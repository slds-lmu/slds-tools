# Confluence Access

Tooling and notes for accessing the **LMU** and (potentially) **MCML** Confluence instances.

> **Status:** working. Read + write round-trip against LMU Confluence proven via
> helper scripts (`smoke-test.sh`, `get-page.sh`, `put-page.sh`, `conf-lib.sh`).
> See **[Usage](#usage)** below.

> ## ⚠️ CRITICAL RULE — do not modify institute content
>
> The LMU Confluence content is **shared by the whole institute and NOT owned by us.**
> **Never create, edit, move, or delete any page** except the explicitly designated
> test page below. No writes to any other page — ever — without a fresh, explicit OK.
>
> **Only writable page:** "BB Test Page" (the dedicated sandbox page).

## Goal

Edit LMU Confluence pages **efficiently and programmatically**, instead of always
going through the web editor by hand. Concretely:

- Verify that Claude Code can reach LMU Confluence with a Personal Access Token (PAT).
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
- **Both new and existing pages.** Create new pages *and* bring existing pages under
  local/Git management.
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

| Instance | Base URL | Type | Auth | Notes |
| -------- | -------- | ---- | ---- | ----- |
| LMU      | `https://collab.dvb.bayern` | Server/Data Center (PAT) | `Authorization: Bearer <PAT>` | primary focus; space `lmustatistics` |
| MCML     | _later_  | _TBD_ | _TBD_ | deferred |

## Access method

Confluence **REST API** over HTTPS.

- Server/DC base path: `<base>/rest/api/...`
- Read a page:   `GET  /rest/api/content/{id}?expand=body.storage,version`
- Update a page: `PUT  /rest/api/content/{id}` (must increment `version.number`)
- Search:        `GET  /rest/api/content/search?cql=...`

**Page body format.** Confluence stores pages in *storage format* (an XHTML dialect),
not Markdown. So a local editing workflow needs a strategy for the body:

1. **Raw storage format** — fetch/edit/push the XHTML as-is. Simplest and *lossless*, but
   verbose and awkward to hand-edit.
2. **Markdown ↔ storage conversion** — edit Markdown locally, convert on push.
   Nicer to edit, but conversion is lossy for macros/layouts.

See **[Better workflows](#better-workflows-markdown--confluence-tools)** for the full
analysis given the two-way requirement.

## Authentication

- PAT already created on LMU Confluence (Server/DC personal access token).
- Sent as `Authorization: Bearer <PAT>` header.
- Secret stored outside the repo (e.g. env var `LMU_CONFLUENCE_PAT` or a gitignored
  `.env` / secrets file). **Never commit the token.**

## Scope

- Start: **read-only smoke test** (fetch one known page) to confirm auth + connectivity.
- Then: **single-page round-trip** (fetch → edit → push, version bump).
- Read/write, limited to spaces the PAT's user can access.

## Usage

All commands run from this directory (`confluence/`). They need the PAT, which the
scripts read from a gitignored `.pat` file or the `LMU_CONFLUENCE_PAT` env var.

### Files

| File | Purpose |
| ---- | ------- |
| `conf-lib.sh`   | Shared helpers (token resolution, authenticated `curl`). Sourced by the others. |
| `smoke-test.sh` | One-shot read-only connectivity/auth check against a known page. |
| `get-page.sh`   | Download a page's storage-format body to a local `.xhtml` file. |
| `put-page.sh`   | Upload a local `.xhtml` body back to a page (auto-increments version). |
| `.pat`          | Your Personal Access Token. **Gitignored — never commit.** |

### 0. One-time setup: provide the token

```bash
# Either drop the PAT into a gitignored file…
printf '%s' 'YOUR_PAT_HERE' > .pat
# …or export it for the shell session:
export LMU_CONFLUENCE_PAT='YOUR_PAT_HERE'
```

Create a PAT in Confluence: avatar → **Settings → Personal Access Tokens → Create token**.
Revoke it there when you're done.

### 1. Read access

Quick connectivity check:

```bash
./smoke-test.sh            # GET a known page, prints JSON + HTTP status
```

Download a page body to edit locally:

```bash
./get-page.sh 2781779130                 # -> page-2781779130.xhtml
./get-page.sh 2781779130 mypage.xhtml    # custom output filename
```

The saved file is the page's **storage format** (Confluence's XHTML dialect), ready
to open in VS Code.

**Finding a page's ID:** it's in the page URL
(`/pages/<ID>/Title`), or search by title:

```bash
source ./conf-lib.sh
conf_curl --get "$CONF_BASE/rest/api/content/search" \
  --data-urlencode 'cql=title="BB Test Page"' | python3 -m json.tool
```

### 2. Write access

```bash
./put-page.sh <page-id> <bodyfile> ["edit message"]
```

- It fetches the current version, increments it, and PUTs the new body.
- **Safety guard:** `put-page.sh` refuses any page except the sandbox
  (ID `2781779130`). To target another page you must *deliberately* set
  `CONF_ALLOW_ANY_PAGE=1` — a friction point on purpose (see the critical rule above).
- ⚠️ **Lost-update risk:** it currently increments from *whatever the latest version is*,
  so if someone edited the page in the web UI after you pulled, your push silently
  overwrites their change. See [the concurrency note](#the-lost-update-problem-shared-pages).

Typical manual round-trip:

```bash
./get-page.sh 2781779130          # 1. pull
code page-2781779130.xhtml         # 2. edit in VS Code, save
./put-page.sh 2781779130 page-2781779130.xhtml "tweak wording"   # 3. push
```

### 3. Editing via Claude Code (the assisted workflow)

The point of this setup: instead of hand-editing XHTML, describe the change and let
CC do it. A session looks like:

1. **You:** "Pull BB Test Page and add a section listing the exam dates."
2. **CC:** runs `./get-page.sh 2781779130`, opens `page-2781779130.xhtml`, edits the
   storage XHTML with its normal file tools (precise, targeted edits — not a blind
   full rewrite), then runs `./put-page.sh 2781779130 page-2781779130.xhtml "..."`.
3. **CC:** re-reads the page to confirm the new version and reports back.

Guidelines for CC in this repo:
- **Never write to any page but the sandbox** without a fresh explicit OK (see the
  critical rule). Reads of any page are fine.
- Prefer **small, surgical edits** to the storage XHTML over regenerating the whole
  body — institute pages use macros/layouts that are easy to clobber.
- Always **re-GET after a PUT** to confirm the version bumped and the change landed.
- Keep a pre-edit copy (the freshly-fetched `.xhtml`) so a bad edit can be reverted
  by PUT-ing the original back.

### 4. Editing manually (no Claude Code, no scripts)

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

- The REST `PUT` uses **optimistic version numbers**. If you pull version *N*, someone
  saves *N+1* in the browser, and you then push *N+1* from your stale copy, **their edit
  is overwritten** with no warning.
- **Mitigation (recommended before any real-page writes):** capture the version at pull
  time and make the push *conditional* — re-GET just before writing and **refuse if the
  version moved** since pull (i.e. set `version.number = pulled + 1` and let Confluence
  reject a stale number, rather than blindly using `current + 1`). Our `put-page.sh`
  currently does the blind thing; this is the first hardening to add when we go beyond the
  sandbox.
- This is also *why* shared pages favour Model A with small surgical edits and a fresh
  pull immediately before each push.

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
- Next concrete steps if you want to proceed: (1) **add the version-guard to `put-page.sh`**
  (the prerequisite for any safe real-page write), (2) install `mark` + `pandoc` via the
  package-manager skill (with manifest), (3) try Model A and a version-guarded `mark`
  Model-B publish on **BB Test Page** to compare the feel.

## Plan / Steps

1. ✅ Capture **base URL** and **PAT handling**; confirmed Server/DC.
2. ✅ **Smoke test:** `smoke-test.sh` GET page 663984308 → `HTTP 200` + JSON
   (auth works, sandbox reaches `collab.dvb.bayern` directly, no VPN).
3. ✅ **Read a page** by ID, save `body.storage` to a local file (`get-page.sh`).
4. ✅ **Round-trip:** modify the local file, `PUT` it back with incremented version,
   verify (`put-page.sh`). Confirmed on BB Test Page (v2 → v5).
5. ⏳ **Add a version-guard** to `put-page.sh` (re-check live version, reject stale writes).
   **Prerequisite for any real-page write** — we never assume sole ownership of a page.
6. ⏳ Answer the **Markdown-fidelity** question (decides how usable Model C is).
7. ⏳ Trial **Model A** and a version-guarded **`mark`** (Model B) on the sandbox.
8. ⏳ (Later) Generalize so CC can act on "edit page X" instructions for real pages
   (still gated by the critical no-touch rule).

### Notes from smoke test (2026-06-08)

- Page body is rich storage-format XHTML: `<ac:layout>` columns,
  `<ac:structured-macro>`, `<ac:link><ri:page>`, emoticons. Hand-editing raw is
  doable but fiddly — argues for eventually doing targeted edits, not full rewrites.
- A write (`PUT`) must set `version.number` to `current + 1` (currently 23 → next 24).

## Reference

- Base URL: `https://collab.dvb.bayern`
- REST base: `https://collab.dvb.bayern/rest/api`
- Read-only example page: ID `663984308` ("Teaching & Exams (Lehre)") — **do not edit.**
- **Writable sandbox page** (the ONLY page we may modify): "BB Test Page",
  ID `2781779130`, space `lmustatistics`, currently empty body.
  URL `https://collab.dvb.bayern/spaces/lmustatistics/pages/2781779130/BB+Test+Page`
- PAT passed via env var `LMU_CONFLUENCE_PAT` (not committed; revoked at end of session).

## Open questions

- **Markdown fidelity (blocking for Model C):** do target pages need multi-column
  layouts / info-warning macros / status badges / structured page links, or is plain
  Markdown enough?
- For two-way on shared pages: is lossless **Model A** (storage XHTML in Git) acceptable
  as the primary workflow, with Markdown reserved for new/simple pages?
