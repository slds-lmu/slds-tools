# CLAUDE.md — publs

Rules of engagement for Claude (or any agent / teammate) modifying this
project. Pair with `architecture.md` (the diagram + invariants) and
`README.md` (the planning doc + workflow).

## Project in one line

Maintain `slds.bib` as the single source of truth for SLDS publications,
by surfacing candidates from external sources for human accept/reject.

## Invariants — do not violate

1. **`slds.bib` is the SSOT.** Hand-edited, version-controlled. Anything
   that needs SLDS publications reads *from* it. Nothing reads ahead of
   it.
2. **Two mutation types only**, both human-confirmed at review time:
   - **append** a new entry (atomic, `open(a) + fsync`)
   - **replace** an existing entry (atomic tmpfile + `os.replace`,
     after diff-confirm). Replace path is described in `architecture.md`
     but not yet implemented.
3. **No wholesale rewrite.** Never reformat, dedupe, reorder, or
   normalize the whole file. Mutations are per-entry.
4. **Author identity is anchored, not searched.** Each source has one
   per-member ID in `members.yaml`. A null ID skips that member on that
   source. There is no name-search fallback anywhere, and there must
   never be one. Past tooling did this and silently put the wrong
   person's papers into the SSOT.
5. **No auto-fill of IDs.** Members.yaml is hand-curated. A previous
   resolver script was deleted on purpose; do not resurrect it.
6. **Coverage gaps are surfaced, not hidden.** Every `check` / `review`
   run ends with a loud yellow warning listing missing IDs per
   platform. This is the only thing keeping skipped members visible —
   keep it loud.
7. **Matching errs toward surfacing.** DOI match first, normalized
   title second; otherwise `missing`. False positives that suppress a
   real paper are far worse than duplicates the user can `r`-reject.
8. **Key collisions rename, never overwrite.** Append uses `-2`/`-3`/...
   suffixes when an ID collides.

## ID-per-platform mapping (single source of truth: `config.py`)

| field         | source        | example                             |
|---------------|---------------|-------------------------------------|
| `openalex_id` | OpenAlex      | `A5012345678`                       |
| `orcid`       | Crossref      | `0000-0000-0000-0000`               |
| `scholar_id`  | Google Scholar| `s34UckkAAAAJ` (the `user=` param)  |

`ID_FIELD_BY_SOURCE` in `src/publs/config.py` is the canonical mapping;
keep new sources in lockstep.

## Source priority

OpenAlex (default, robust, parsed JSON) → Crossref (DOI-centric, TBD)
→ Google Scholar (last; blocks easily, must be opt-in via `--source
scholar`, TBD).

## Implementation status

- done: OpenAlex source, match, append-on-accept, interactive review
- TBD:  Crossref source
- TBD:  Scholar source (must be explicit `--source scholar`)
- TBD:  Replace path for `divergent` matches (per architecture.md)
- TBD:  `publs lint` for SSOT hygiene (URL fields with HTML, missing DOIs, etc.)

## Rejected approaches (don't propose these again)

- **Per-member output files** (`out/<lastname>.bib`). Old design, scrapped.
  One SSOT, period.
- **Name-search fallback** when an ID is missing. Caused 100%-missing
  misfires (343 papers by the wrong Andreas Bender). Removed permanently.
- **ORCID lookup as a fallback for OpenAlex ID.** Fewer surprises to
  just require the explicit `openalex_id`; ORCID has its own slot for
  Crossref.
- **Auto-resolver script** for IDs. Existed briefly, deleted; manual
  curation of `members.yaml` is the contract.
- **Hard-fail on missing IDs.** Considered briefly; the "skip + loud
  warning" model wins because it lets you make progress on members
  whose IDs *are* set.
- **Whole-file rewrites of `slds.bib`** (reformat, dedupe, key reorder,
  field normalization). Hand-edits and tool-edits must coexist.
- **Scrapingdog / Playwright / browser automation for Scholar.** Old
  design, scrapped along with per-member output. If Scholar lands, it's
  a clean source module, not a scraper-with-CAPTCHA-handling.

## Where things live

- `members.yaml` — SSOT for member identities. Hand-curated.
- `slds.bib` — SSOT for publications. Hand-curated; tool appends only.
- `config.yaml` — `ssot_path`, `min_year`, `mailto`, `enabled_sources`.
- `src/publs/` — the package; module roles documented in
  `architecture.md`.

## Working agreements

- Default to writing no comments. Module docstrings explain WHY; in-line
  comments only when behaviour would surprise a reader.
- Don't ship Python files purely as scaffolding for "the next phase."
  Add modules when the code that needs them lands.
- The README is for planning conversations. `architecture.md` describes
  the system. This file (`CLAUDE.md`) describes the contract. Keep them
  in their lanes.
