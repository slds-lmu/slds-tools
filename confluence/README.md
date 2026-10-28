# Confluence Access

Tooling and notes for accessing the **LMU Stats** and (potentially) **MCML** spaces of the LMU Confluence instance.

> **Status:** working. Read + write round-trip with version guard, page creation, page
> tree, version history and search proven against LMU Stats Confluence (2026-10-21).
> See **[Usage](#usage)** below.

> ## ⚠️ CRITICAL RULE — do not modify institute content
>
> The LMU Confluence content (in both spaces) is **shared by the whole institute / all of
> MCML and NOT owned by us.** **Never create, edit, move, or delete any page** except
> inside the explicitly designated sandbox below. No writes to any other page — ever —
> without a fresh, explicit OK.
>
> **Only writable pages:** "BB Test Page" (the dedicated sandbox page) and its subpages.

## Goal

Edit LMU Confluence pages **efficiently and programmatically**, instead of always
going through the web editor by hand. Concretely:

- Verify that Claude Code can reach the LMU Stats Confluence with a Personal Access Token (PAT).
- Pull page content down locally (ideally into VS Code), edit it, and push it back.
- Let Claude Code assist: give natural-language instructions like "edit page X to do Y"
  and have CC make the change against the live Confluence page.

MCML is out of scope for now (revisit later).

## Requirements (from discussion, 2026-06-08)

- **Shared, multi-author pages.** These are worked on by the whole institute; **most
  people use the web editor.** Goal is to work *more efficiently* than the web editor —
  without disrupting everyone else.
- **Two-way is required.** Not just Git → Confluence publishing — we must also be able to
  **pull web edits back**. (This is the hard constraint; see the reality check below.)
- **Both new and existing pages.** Create new pages (and add them to confluence / push
  them) *and* bring existing pages under local/Git management.
- **No assumption of sole ownership.** Even a page *we* create lives in a shared space and
  may be edited by anyone via the web UI at any time. **Never treat a local copy as
  authoritative, and never use blind overwrite publishing.** Every write must detect and
  respect concurrent changes (a version-guard / optimistic-concurrency check). This applies
  to *all* pages, not only the obviously-shared ones.
- **Markdown fidelity: undecided.** Not yet known whether pages need the fancy Confluence
  stuff (multi-column layouts, info/warning macros, status badges, page links) or whether
  plain Markdown (headings, lists, tables, code, images, links) is enough. This is the
  single biggest factor in how clean any Markdown conversion can be.
- **Install freedom.** We may install whatever tooling we like locally
  (still tracked via the `system-package-manager` skill + manifest).
- **Editing surface: VS Code *and* Obsidian both welcome.**

## Targets

Both spaces live on the same Confluence instance (BayernCollab, Confluence Data Center
9.2.26), so one access token is used for both — and every other space your LMU account can access.

| Space | Base URL | Type | Auth | Notes |
| ----- | -------- | ---- | ---- | ----- |
| LMU Stats | `https://collab.dvb.bayern` | Data Center 9.2.26 (PAT) | `Authorization: Bearer <PAT>` | primary focus; space `lmustatistics` |
| MCML     | `https://collab.dvb.bayern` | same instance | same PAT | space `LMUMMCFML`; deferred and NOT TESTED |

## Access method

Confluence **REST API** over HTTPS (see [Documentation](#documentation) below).

- Server/DC base path: `<base>/rest/api/...`
- Read a page:   `GET  /rest/api/content/{id}?expand=body.storage,version,ancestors`
- Update a page: `PUT  /rest/api/content/{id}` (`version.number` must be exactly
  current + 1, otherwise rejected)
- Create a page: `POST /rest/api/content` (parent via `ancestors`)
- Page tree:     `GET  /rest/api/content/search?cql=type=page and ancestor={id}`, or
  for a whole space: `GET /rest/api/space/{key}/content/page?depth=all` 
- Version history:  `GET  /rest/experimental/content/{id}/version` (undocumented, see
  [below](#instance-quirks-bayerncollab-confluence-9226))
- Old version:   `GET  /rest/api/content/{id}?status=historical&version={n}`
- Full-text search: `GET  /rest/api/search?cql=...&excerpt=highlight`

**Page body format.** Confluence stores pages in *storage format* (an XHTML dialect),
not Markdown. So a local editing workflow needs a strategy for the body:

1. **Raw storage format** — fetch/edit/push the XHTML as-is. Simplest and *lossless*, but
   verbose and awkward to hand-edit.
2. **Markdown ↔ storage conversion** — edit Markdown locally, convert on push.
   Nicer to edit, but conversion is lossy for macros/layouts.

See **[Better workflows](#better-workflows-markdown--confluence-tools)** for the full
analysis given the two-way requirement.

## Authentication

- PAT created on LMU Confluence (Server/DC personal access token).
- Sent as `Authorization: Bearer <PAT>` header.
- Secret stored outside the repo (e.g. env var `LMU_CONFLUENCE_PAT` or a gitignored
  `.env` / secrets file). **Never commit the token.**
- Setup: see [below](#0-one-time-setup-provide-the-token).

## Scope

- Start: **read-only smoke test** (fetch one known page) to confirm auth + connectivity.
- Then: **single-page round-trip** (fetch → edit → push, version bump).
- Read/write, limited to spaces the PAT's user can access.

## Usage

All commands run from this directory (`confluence/`). They need the PAT, which the
scripts read from a gitignored `.pat` file or the `LMU_CONFLUENCE_PAT` env var.
Local paths — where pulled pages go (`-d <pages-dir>`) and the exclude list
(`-x <exclude-file>`) — are always passed explicitly to the scripts.

### Files

| File | Purpose |
| ---- | ------- |
| `conf-lib.sh`     | Shared helpers (token resolution, authenticated `curl`, handling exclude list). Sourced by the others. |
| `smoke-test.sh`   | One-shot read-only connectivity/auth check against a known page. |
| `get-page.sh`     | Download a page into `<pages-dir>`: a working copy, an untouched copy, and version metadata. |
| `put-page.sh`     | Push an existing working copy back, guarded against concurrent edits; shows the diff. |
| `create-page.sh`  | Create a subpage from `.xhtml` or `.md` (via pandoc), pushes and pulls new online page back. |
| `page-tree.sh`    | Page tree below some page, as Markdown (titles only). |
| `page-history.sh` | Complete version history of a page: number, date, author, edit message. |
| `search.sh`       | Full-text search (CQL) with excerpts. |
| `.pat`            | Your Personal Access Token. **Gitignored — never commit.** |
| `.claude/settings.json` | Denies Claude Code's file tools access to `.pat` and `.env`. |

### 0. One-time setup: provide the token

Create a PAT in Confluence: Avatar → **Settings → Personal Access Tokens → Create token**.
Set an **expiry** (e.g. 1–2 weeks): a PAT has *all* the permissions of your account and
cannot be restricted to certain pages or spaces, so a short lifetime is the main
protection. Revoke it there when you're done.

```bash
# Either drop the PAT into a gitignored file, but without leaking to shell history…
read -rs pat && printf '%s' "$pat" > .pat
# …or export it for this shell session:
export LMU_CONFLUENCE_PAT='YOUR_PAT_HERE'
```

Do not have the token enter the chat session, also not by invoking a command inside the session.
The scripts never print the token and don't expose it.
Don't use `curl -v` with `conf_curl`, since it prints the `Authorization` header.

### 1. Read access

Quick connectivity check:

```bash
./smoke-test.sh            # GET a known page, prints JSON + HTTP status
```

Download a page to edit locally:

```bash
./get-page.sh -d <pages-dir> [-x <exclude-file>] [-f] <page-id>
```

It writes three files into `<pages-dir>`, identified by page ID:

| File | Purpose |
| ---- | ------- |
| `<id>_<title>.xhtml`        | working copy — edit this one |
| `<id>_<title>.pulled.xhtml` | untouched copy as pulled — for the diff and for reverting |
| `<id>_<title>.meta.json`    | Metadata: title, space, URL, ancestors, version (number, time, author, message), pull time |

- `-x`: refuses pages in the exclude list (or subpages of excluded pages).
- Refuses to overwrite an already existing working copy that has local edits; `-f` forces it.
- The saved body is the page's **storage format** (Confluence's XHTML dialect), ready to open in VS Code.

**Finding a page's ID:** it's in the page URL (`/pages/<ID>/Title`), in the output of
`page-tree.sh`, or via `search.sh`.

### 2. Write access

```bash
./put-page.sh -d <pages-dir> [-n] <page-id> "<edit message>"
```

- Pushes `<pages-dir>/<id>_<title>.xhtml`. The edit message is required (non-empty);
  it shows up in the page history.
- **Version guard:** re-GETs the live page and refuses if its version number or last-edit
  time differs from the local copy, i.e., if someone edited it since the pull.
  In this case, you must save your edits, pull again (`-f`) and redo them.
  The PUT sends `version = pulled + 1`, so Confluence itself rejects (HTTP 409) an edit
  that lands between the check and the write.
- Prints the diff against the `.pulled` copy; `-n` stops there (dry run).
- After the push it re-pulls the page, so the local files and `.meta.json` match the new
  version.
- **Safety guard:** Currently refuses any page outside the sandbox (BB Test Page and subpages).
  To target another page you must *deliberately* set `CONF_ALLOW_ANY_PAGE=1` — a friction
  point on purpose (see the critical rule above).

Typical manual round-trip:

```bash
./get-page.sh -d <pages-dir> 2781779130                      # 1. pull
code <pages-dir>/2781779130_BB-Test-Page.xhtml                # 2. edit in VS Code, save
./put-page.sh -d <pages-dir> -n 2781779130 "tweak wording"    # 3. check the diff
./put-page.sh -d <pages-dir> 2781779130 "tweak wording"       # 4. push
```

### 3. Creating a page

```bash
./create-page.sh -d <pages-dir> <parent-id> "<title>" [bodyfile]
```

- Confluence assigns the page ID. Titles must be unique within a space (otherwise rejected).
- `bodyfile`: storage XHTML, or Markdown (`*.md`), converted locally to XHTML with
  `pandoc -f gfm -t html` — plain structure only (headings, lists, tables, links, code),
  no Confluence macros.
  Default: empty page.
- Then pulls the new page into `<pages-dir>`; from there on it is edited like any other.
- Same safety guard as `put-page.sh`: the parent must be in the sandbox.

### 4. Finding information: tree, history, search

```bash
./page-tree.sh <root-page-id | space-key> > <file>.md   # Markdown tree: titles, IDs, versions
./page-history.sh [-x <exclude-file>] <page-id>         # lists all versions, newest first
./search.sh [-x <exclude-file>] [-s <space-key>] [-a <ancestor-id>] [-n <max>] "<text>"
```

- `page-tree.sh` fetches titles and version info only, never page contents, so it has no
  exclude option. Sorted like the web UI.
- `search.sh`: default space `lmustatistics`; `-a` restricts to a subtree; all results by
  default, each page only once, with highlighted excerpts. Matches word forms too (e.g. "exam" also
  finds "exams").

**Exclude list** (`-x`): a text file with one page ID per line, `#` starts a comment. An
excluded page *and its whole subtree* are never downloaded (`get-page.sh`), searched
(`search.sh`), or their history listed (`page-history.sh`). Of course, the PAT could
still do all of this, only the scripts refuse to.

### 5. Editing via Claude Code (the assisted workflow)

The point of this setup: instead of hand-editing XHTML, describe the change and let
CC do it. A session looks like:

1. **You:** "Pull BB Test Page and add a section listing the exam dates."
2. **CC:** runs `./get-page.sh -d <pages-dir> 2781779130`, edits the working copy with its
   normal file tools (precise, targeted edits — not a blind full rewrite), shows the diff
   with `./put-page.sh -n ...`.
3. **CC:** pushes with `put-page.sh`, which re-pulls the page, confirming the new version,
   and CC reports back.

Guidelines for CC in this repo:
- **Never write to any page outside the sandbox** without a fresh explicit OK (see the
  critical rule). Reads of any page are fine — except those in the exclude list: always
  pass `-x` when one exists.
- Prefer **small, surgical edits** to the storage XHTML over regenerating the whole
  body — institute pages use macros/layouts that are easy to clobber.
- Never use `-f` (overwrites local edits) or `CONF_ALLOW_ANY_PAGE=1` without asking.
- A bad edit can be reverted from the `.pulled` copy of the previous version, or from the
  page history.

### 6. Editing manually (no Claude Code, no scripts)

You can also talk to the API directly, or skip the API entirely:

- **Plain web editor:** just edit the page in the browser. Nothing here changes that.
- **VS Code + scripts:** the `get-page.sh` / `put-page.sh` pair above is the
  lightweight "edit locally" path — no extra tooling needed.
- **Raw curl** (what the scripts wrap), e.g. a read:

  ```bash
  curl -sS -H "Authorization: Bearer $LMU_CONFLUENCE_PAT" \
    "https://collab.dvb.bayern/rest/api/content/2781779130?expand=body.storage,version"
  ```

- **VS Code Atlassian extension** (optional, not set up here): there are
  marketplace extensions that browse/edit Confluence in the editor. Viable if you
  want a GUI inside VS Code, but the script path keeps content as plain files in git.

> **Body format reminder.** Pages are stored as XHTML *storage format*, not Markdown.
> Hand-editing is fine for text and simple structure; be careful around
> `<ac:structured-macro>`, `<ac:layout>`, and `<ac:link>` elements.

## Better workflows: Markdown ↔ Confluence tools

The raw `get-page.sh`/`put-page.sh` flow works but is unpleasant: you hunt for numeric
IDs, edit verbose XHTML, and (if you only diff XHTML) get awkward version history. Below
is the full landscape of alternatives, framed by **our two hard constraints: two-way
sync, on shared multi-author pages.**

### Reality check: two-way + shared pages is the hard case

There are two independent problems, and most tools solve only the first:

1. **Format conversion** (XHTML storage ↔ Markdown). Markdown→storage is fairly good;
   storage→Markdown is **lossy** — macros, `<ac:layout>` columns, emoticons, status
   badges, structured links degrade or vanish.
2. **Concurrency / merge.** Because others edit via the web UI, any local copy goes
   **stale**. A push must not blindly overwrite newer web edits.

**Consequence:** a *lossless* two-way workflow basically requires keeping the **storage
XHTML itself** as the local canonical format (no conversion), because only then does
"pull → edit → push" round-trip without information loss. The moment you introduce
Markdown as the local format, two-way becomes *best-effort* and you accept drift on
anything richer than plain text. There is **no mature tool that does clean, lossless,
two-way Markdown ↔ Confluence sync** for arbitrary macro-rich pages — this is a real
limitation, not a gap in our setup.

### Three workable models

| Model | Local format | Direction | Fidelity | Good for | Tooling |
| ----- | ------------ | --------- | -------- | -------- | ------- |
| **A. Storage-in-Git** | storage XHTML | **true 2-way, lossless** | ✅ full | shared/existing macro-rich pages | our `get-page.sh`/`put-page.sh` (+ version guard) |
| **B. Markdown publish** | Markdown | 1-way render (Git → Confluence) | n/a (we render) | drafting/seeding **new** pages | `mark`, `md2cf` (+ version guard) |
| **C. Markdown 2-way** | Markdown | best-effort 2-way | ⚠️ lossy | simple, text-only pages | pull: pandoc/exporter · push: `mark`/`md2cf` |

**Caveat on Model B — there is no "page we own".** Because anyone can edit any page in the
web UI, even a page you created with `mark` can be changed by a colleague afterwards.
Re-publishing from Git would then **silently overwrite their edit**. So Model B is only
safe as a *seeding/drafting* step (create the first version), or when its push is wrapped
in the same **version-guard** as Model A so a concurrent change aborts the write instead of
clobbering it. Treat one-way publish as "I assert this content" only after confirming the
live page hasn't moved.

Given your requirements (2-way **and** shared pages **and** both new+existing, with **no
ownership assumption**), the realistic answer is a **mix**: **Model A as the safe default
for anything that already exists or is shared**, **Model B only to seed brand-new pages
(still version-guarded)**, and **Model C only for simple pages** where you've accepted the
conversion loss. The Markdown-fidelity question you left open decides how much of C is
usable.

### Tool catalog

#### Push: Markdown → Confluence

| Tool | Install | DC + PAT? | Metadata / IDs | Notes |
| ---- | ------- | --------- | -------------- | ----- |
| **mark** (`kovetskiy/mark`) | Go single binary | ✅ yes | HTML-comment header (`Space`/`Title`/`Parent`) | Most mature publisher; supports info/warning/code/mermaid/TOC macros via fenced conventions. One-way. |
| **md2cf** (`iamjackg/md2cf`) | `pip`/`uv` (Python) | ✅ yes (`--token`) | mirrors a directory tree to a page tree; can record page IDs | Good for multi-page doc sets. One-way. |
| **markdown-confluence** (`@markdown-confluence/publish`) | Node / Obsidian plugin | ⚠️ Cloud-focused; DC unreliable | Obsidian frontmatter | Best if you live in Obsidian *and* on Cloud. Probably not us (we're DC). |
| **sphinxcontrib-confluencebuilder** | `pip` (Sphinx) | ✅ yes | Sphinx project config | Publishes reStructuredText/Sphinx docs to Confluence. Relevant only if docs are reST, not MD. One-way. |

#### Pull / export: Confluence → Markdown

| Tool | Install | Quality | Notes |
| ---- | ------- | ------- | ----- |
| **pandoc** (`-f html -t gfm`) | binary | rough | Feed it a fetched storage body; macros/layouts come out as noise → hand cleanup. Best-effort *import*, not sync. |
| **confluence-markdown-exporter** (e.g. `Spenhouet/confluence-markdown-exporter`) | `pip` | varies | Bulk-export spaces/pages to Markdown; quality depends on macro usage. Export only. |
| **confluence-to-markdown** (various node/py projects) | node/py | varies | Similar bulk exporters; one-shot migration aids, not round-trip. |
| Built-in Confluence export | none | n/a | Page → **Export to Word/PDF/HTML**; then convert with pandoc. Manual, for archival/import. |

#### Server-side conversion (no install)

- `POST /rest/api/contentbody/convert/storage` converts a body from **`wiki`** or
  **`editor`** representation into **`storage`**. Useful if you'd rather write Confluence's
  own lighter *wiki markup* and let the server produce storage — but the input is **not
  Markdown**, so it doesn't give the Markdown-in-Git experience.

#### GUI / editor integrations (not file/Git based)

- **VS Code "Confluence"/Atlassian extensions** — browse & edit pages inside VS Code.
  Convenient, but content lives in Confluence, not as plain files in Git.
- **Obsidian + markdown-confluence plugin** — Markdown GUI, but Cloud-oriented.
- **Plain web editor** — always available; the correct choice for shared institute pages.

### How `mark` and `md2cf` actually work (step by step)

Both follow the same idea: **a Markdown file is the source; the tool converts it to
storage format and pushes it to a specific page via the REST API.** Neither pulls changes
back — they are *publishers*, not sync engines.

#### `mark` — page identity lives in the file header

1. You write a normal Markdown file with a small block of **HTML-comment directives** at
   the top that tell `mark` where the page goes:

   ```markdown
   <!-- Space: lmustatistics -->
   <!-- Parent: Teaching & Exams (Lehre) -->
   <!-- Title: My New Page -->

   # My New Page

   Normal **Markdown**: tables, code blocks, images, links all convert.

   <!-- include macros via fenced blocks, e.g. an info panel: -->
   ```

2. You run it (PAT as the password on Data Center):

   ```bash
   mark -u "$USER" -p "$LMU_CONFLUENCE_PAT" \
        -b https://collab.dvb.bayern -f mypage.md
   ```

3. What it does under the hood:
   - Resolves the target page by **Space + Title** (creating it under **Parent** if it
     doesn't exist, or updating it if it does) — *you never type a numeric ID.*
   - Converts Markdown → Confluence **storage XHTML** (its converter handles headings,
     lists, tables, code blocks, images, and a set of macros: info/note/warning panels,
     `code`, `mermaid`, table-of-contents, etc. via fenced-code conventions).
   - `PUT`s the new body and bumps the version, exactly like our `put-page.sh` — `mark`
     is essentially "Markdown conversion + ID resolution" layered on the same REST call.
   - Optionally writes the resulting page ID/URL back to stdout so you can record it.

   **Round-trip reality:** edit `mypage.md`, re-run `mark`, page updates. But if someone
   edited that page in the browser meanwhile, re-running `mark` **overwrites** their change
   — same lost-update caveat as below. Markdown is the master; the web copy is disposable.

#### `md2cf` — directory tree mirrors page tree

1. Install: `pip install md2cf` (or `uv tool install md2cf`).
2. Point it at a file or a folder:

   ```bash
   md2cf --host https://collab.dvb.bayern/rest/api \
         --token "$LMU_CONFLUENCE_PAT" \
         --space lmustatistics \
         mypage.md                 # or a whole directory
   ```

3. What it does:
   - Converts each Markdown file → storage and `PUT`/`POST`s it via REST.
   - When given a **directory**, it recreates the folder structure as a **page hierarchy**
     (parent/child pages), which is handy for publishing a whole doc set at once.
   - Can be told the page **title** (from the first `#` heading or a flag) and can record
     the created page **IDs** so subsequent runs update instead of duplicating.
   - Supports PAT/bearer auth → works against our Data Center instance.

   Like `mark`, it's **one-way**: Markdown → Confluence, master is your local files.

#### Why neither gives clean two-way

The return trip (Confluence storage → Markdown) is the lossy half (macros/layouts don't
survive). So "edit in the browser, pull back into Markdown, keep editing locally" is not
something these tools do reliably. For the **shared pages where colleagues edit in the web
UI**, that's why **Model A (storage XHTML in Git)** — not `mark`/`md2cf` — is the safe
two-way option; `mark`/`md2cf` are best for **seeding a brand-new page's first version**
(Model B), and even then their push should be version-guarded, because once the page
exists anyone may edit it — we never solely own it.

### The lost-update problem (shared pages)

Because colleagues edit via the web UI, this matters more than format:

- The REST `PUT` uses **optimistic version numbers**: Confluence only accepts
  `version.number = current + 1` and answers HTTP 409 otherwise. So if you pull
  version *N*, someone saves *N+1* in the browser, and you then push *N+1* from your stale
  copy, Confluence rejects it.
- The real risk is a client that reads the *current* version right before pushing and
  sends `current + 1` — that always succeeds and **silently overwrites** the other edit.
  Tools like `mark`/`md2cf` might behave the same way.
- This is also *why* shared pages favour Model A with small surgical edits and a fresh
  pull immediately before each push.
- **Our mitigation** (inside `put-page.sh`): record the version at pull time (`.meta.json`),
  re-GET just before writing and **refuse if version number or edit time moved**, and send
  `pulled + 1` so Confluence also rejects anything that slips in between.

### Recommendation

- **Default for everything → Model A** (storage XHTML in Git via our scripts), with the
  **version-guard** added, and Claude Code doing the editing from natural language so you
  never hand-write XHTML. Lossless and safe for multi-author pages.
- **Seeding a brand-new page → Model B** with **`mark`** (draft Markdown, publish the first
  version) — but **still version-guarded**, since the page is shared the moment it exists.
- **Model C (Markdown 2-way)** only after we answer the **fidelity** question — fine for
  plain text/list/table pages, not for macro/layout-heavy ones.
- **Non-negotiable across all models:** writes use optimistic concurrency — re-check the
  live version immediately before pushing and **abort on any concurrent change** rather
  than overwrite. We never assume sole ownership of a page.
- Next concrete steps if you want to proceed: (1) ✅ version-guard to `put-page.sh`
  (the prerequisite for any safe real-page write) -> **already done**, (2) install `mark` + `pandoc` via the
  package-manager skill (with manifest), (3) try Model A and a version-guarded `mark`
  Model-B publish on BB Test Page to compare the feel.

## Plan / Steps

1. ✅ Capture **base URL** and **PAT handling**; confirmed Server/DC.
2. ✅ **Smoke test:** `smoke-test.sh` GET page 663984308 → `HTTP 200` + JSON
   (auth works, sandbox reaches `collab.dvb.bayern` directly, no VPN).
3. ✅ **Read a page** by ID, save `body.storage` to a local file (`get-page.sh`).
4. ✅ **Round-trip:** modify the local file, `PUT` it back with incremented version,
   verify (`put-page.sh`). Confirmed on BB Test Page (v2 → v5).
5. ✅ **Add a version-guard** to `put-page.sh` (re-check live version, reject stale writes).
   Tested 2026-10-21 on BB Test Page.
6. ✅ **Local files + metadata**
   in a given pages directory (`get-page.sh -d`), diff and dry run before push, re-pull after push.
7. ✅ **Page tree, version history, search** (`page-tree.sh`, `page-history.sh`,
   `search.sh`) incl. the exclude list.
8. ⏳ Answer the **Markdown-fidelity** question (decides how usable Model C is).
9. ⏳ Trial **Model A** and a version-guarded **`mark`** (Model B) on the sandbox.
10. ⏳ (Later) Generalize so CC can act on "edit page X" instructions for real pages
    (still gated by the critical no-touch rule).

### Notes from smoke test (2026-06-08)

- Page body is rich storage-format XHTML: `<ac:layout>` columns,
  `<ac:structured-macro>`, `<ac:link><ri:page>`, emoticons. Hand-editing raw is
  doable but fiddly — argues for eventually doing targeted edits, not full rewrites.
- A write (`PUT`) must set `version.number` to exactly `current + 1`; anything else is
  rejected with HTTP 409.

## Instance quirks (BayernCollab, Confluence 9.2.26)

Found while testing on 2026-10-21.

- `GET /rest/api/content/{id}/descendant/page` answers HTTP 500 (even without
  parameters), in contrast to official documentation → Our scripts use CQL `ancestor = {id}`
  instead. `/descendant` (without `/page`) and `/child/page` work.
- `GET /rest/experimental/content/{id}/version` (complete version history of a page incl
  author, time, message) is **not in the documented 9.2 API, but still works** → used by
  `page-history.sh`. The documented `/rest/api/content/{id}/version` doesn't exist.
- Errors usually come as JSON with `statusCode`; unknown paths answer with `status-code`
  instead.
- Updates (pushes) don't need the `space` field (accepted without it); a nonexistent space
  key is rejected with HTTP 400. Danger: With a *different existing* space the page might be moved
  (this was NOT TESTED ON PURPOSE) → `put-page.sh` doesn't use the `space` field.
- Converted Markdown (to plain HTML) pages are accepted as new pages almost unchanged; only `id`
  attributes on headings are dropped.

## Reference

- Base URL: `https://collab.dvb.bayern`
- REST base: `https://collab.dvb.bayern/rest/api`
- Read-only example page: ID `663984308` ("Teaching & Exams (Lehre)") — **do not edit.**
- **Writable sandbox** (the ONLY pages we may modify): "BB Test Page",
  ID `2781779130`, space `lmustatistics`, **and its subpages**.
  URL `https://collab.dvb.bayern/spaces/lmustatistics/pages/2781779130/BB+Test+Page`
- PAT read from `.pat` or env var `LMU_CONFLUENCE_PAT` (not committed; short expiry,
  revoked at end of session).

### Documentation

- [Confluence Data Center REST API 9.2.3](https://developer.atlassian.com/server/confluence/rest/v923/intro/)
  — closest documented version to our 9.2.26;
  [OpenAPI spec](https://dac-static.atlassian.com/server/confluence/9.2.3.swagger.v3.json)
  (machine-readable, all endpoints + parameters).
- [Latest Data Center REST API (v1000)](https://developer.atlassian.com/server/confluence/rest/v1000/intro/);
  the [older overview page](https://developer.atlassian.com/server/confluence/confluence-server-rest-api/)
  covers only Server 5.5–8.5.
- [Using Personal Access Tokens](https://confluence.atlassian.com/enterprise/using-personal-access-tokens-1026032365.html)
  (Data Center; expiry, permissions = those of the creating user). Part of the general
  [Atlassian Data Center documentation](https://confluence.atlassian.com/enterprise/atlassian-data-center-documentation-892801292.html)
  (admin docs, not the API).
- [Advanced searching using CQL](https://developer.atlassian.com/server/confluence/advanced-searching-using-cql/)
- [Confluence storage format](https://confluence.atlassian.com/doc/confluence-storage-format-790796544.html)
- [KB: retrieve all previous versions of content via REST](https://confluence.atlassian.com/confkb/how-to-retrieve-all-previous-versions-of-content-using-the-rest-api-1044789048.html)

## Open questions

- **Markdown fidelity (blocking for Model C):** do target pages need multi-column
  layouts / info-warning macros / status badges / structured page links, or is plain
  Markdown enough?
- For two-way on shared pages: is lossless **Model A** (storage XHTML in Git) acceptable
  as the primary workflow, with Markdown reserved for new/simple pages?
- Same token + exact same setup should work for MCML Confluence space, not tested yet
