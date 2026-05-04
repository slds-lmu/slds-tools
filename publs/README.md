# publs

Scrape SLDS member publications from Google Scholar into one BibTeX file per
member. Configurable via two YAML files; cached on disk so repeated runs are
cheap and a CAPTCHA mid-run doesn't lose what's already been fetched.

## Install

```bash
cd publs
uv sync
```

## Configure

1. **`members.yaml`** — list of SLDS people. Pre-seeded from the chair website
   on 2026-05-04. For each person you care about, fill in their Google Scholar
   `user=` ID:

   ```yaml
   - name: Bernd Bischl
     role: Chair
     scholar_id: s34UckkAAAAJ        # the value of `user=` in their profile URL
   ```

   Members with `scholar_id: null` are skipped with a warning. Set
   `include: false` to hide a member without removing the entry.

2. **`config.yaml`** — global knobs:
   - `min_year` — drop older publications (`null` = keep all)
   - `cache_ttl_days` — how long a cached fetch is considered fresh
   - `proxy` — `none` (default) or `free`
   - `delay_between_members` — politeness delay between members (seconds)
   - `delay_between_pubs` — politeness delay between per-pub BibTeX
     fetches (seconds; this is the dominant cost on big author profiles)

## Use

```bash
# 1. List members and which have Scholar IDs configured.
uv run publs list

# 2. Pull from Google Scholar into cache/.
uv run publs fetch                    # all members; resumes any partial cache
uv run publs fetch --member bischl    # single person
uv run publs fetch --force            # ignore cache TTL, refetch listings
uv run publs fetch --no-bibtex        # phase 1 only (listings, no per-pub BibTeX)

# 3. Render cache/ into out/<lastname-firstname>.bib
uv run publs render
uv run publs render --member bischl
```

`fetch` and `render` are decoupled: change `min_year` and re-run `render` to
get new `.bib` files in seconds without re-hitting Scholar.

## Scraping strategy (read this before debugging fetch failures)

Google Scholar has no public API and aggressively discourages automated
access. Building this tool is a fight against that. The strategy below is
shaped entirely by what Scholar will actually let you do.

### The two-phase data model

Scholar splits the data we want across two surfaces, with very different
properties:

| Phase | What it gives us | Cost | Reliability |
|---|---|---|---|
| **1. Author profile listing** | Title, year, co-author string, venue string, citation_id — for every pub on the profile | **1 request per member** | Robust. Bischl's 337 pubs come down in seconds; doesn't usually trigger CAPTCHA. |
| **2. Per-pub BibTeX** | A real `@article{...}` entry with full first names, journal, volume, pages, etc. | **2 requests per pub** (search + cite popup) | Fragile. Triggers CAPTCHA quickly. Title-search can also match the wrong paper for very common titles. |

The reason BibTeX is so expensive: on author profiles, Scholar's "Cite"
button is JavaScript-only — the popup URL isn't in the page HTML, only
constructed client-side when a real human clicks. We therefore work around
it by searching Scholar by title (which *does* return a snippet whose cite
popup URL is in the HTML), then fetching BibTeX from that snippet. Two
requests per pub instead of one. The Python `scholarly` library does support
`bibtex()` directly, but only on search-result snippets — calling it on an
author-profile publication crashes with `KeyError: 'ENTRYTYPE'` (upstream
bug; the cite URL is missing for that publication source).

### CAPTCHA, not rate-limiting

Once Scholar flags your IP it serves a CAPTCHA on every search-style request
for hours, sometimes a day. It is not "wait 60 seconds and retry." The only
reliable mitigations are:

- **A real browser with `chromium-driver` installed** — `scholarly`'s
  fallback path can auto-solve simple CAPTCHAs in selenium. Hard CAPTCHAs
  (image grids) still need a human.
- **A paid proxy pool** (ScraperAPI, ScrapeOps, Bright Data) — cycles IPs
  faster than Google can blacklist them. Not currently wired into this
  tool; would be ~10 lines in `configure_proxy`.
- **Wait it out**, then resume. The incremental cache makes this feasible.

### Incremental cache + resume

Because phase 2 is so likely to be interrupted, the cache is written **after
every successful per-pub BibTeX fetch** (atomically, via tmpfile + rename).
Concretely this means:

- A CAPTCHA on Bischl's pub 200 of 276 doesn't lose pubs 1..199 — they're
  already on disk.
- Re-running `publs fetch --member bischl` after a block picks up exactly
  where it stopped: it loads the existing cache, sees which pubs already
  have a BibTeX string, and only requests the rest.
- Pubs below `min_year` are skipped in phase 2 entirely — no point spending
  Scholar requests on entries the renderer would drop anyway.
- `--force` clears the resume state and refetches the listing from scratch.

### Practical recipe for a fresh run

1. **Phase 1 only first**, for everyone:
   ```bash
   uv run publs fetch --no-bibtex
   ```
   One request per member; very unlikely to trigger CAPTCHA. After this
   you have full publication *lists* for all members in `cache/`.

2. **Render now if you just need titles/years/venues** — the entries
   without BibTeX get skipped, but you can extend the renderer to fall
   back on a locally-built `@article{...}` from the listing fields if
   you want something now.

3. **Phase 2 in chunks**, one member at a time, with patience:
   ```bash
   uv run publs fetch --member bischl
   # Wait, watch the log. If CAPTCHA hits, kill it, wait several hours,
   # then re-run the same command — it resumes from the cache.
   uv run publs fetch --member bothmann
   # ...
   ```

4. If your IP gets blocked early and you need entries today, fall back to
   the local-build path (planned, not yet implemented — see "Open work"
   below).

## Output

```
out/
  bischl-bernd.bib
  bothmann-ludwig.bib
  ...
```

Each file is a normal BibTeX file you can `\bibliography{out/bischl-bernd}`
or `\input{out/bischl-bernd.bib}` into your TeX project. Files start with a
`%`-comment header recording the Scholar ID, fetch timestamp, and active
filters — handy for spotting stale output.

## Open work

- **Local-build BibTeX fallback** — assemble `@article{...}` entries
  mechanically from the phase-1 listing data (title, author string, year,
  venue) when phase-2 BibTeX is unavailable. Lower fidelity (initials not
  full first names, no DOI), but works without any Scholar requests for the
  BibTeX step. The right escape hatch when CAPTCHA is sustained.
- **Paid-proxy backend** in `configure_proxy` — `proxy: scraperapi` keyed
  off an env var. Worth doing if phase 2 becomes a regular need.
- **Title-match verification** in `fetch_pub_bibtex` — the search-then-cite
  path currently takes the first hit without checking that title and year
  agree. Common titles risk wrong-author entries.
