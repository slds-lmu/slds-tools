# publs

Maintain **one** BibTeX file (`slds.bib`) as the single source of truth for all
SLDS publications, and keep it complete by interactively reviewing candidates
suggested by external publication databases.

## Why this exists

SLDS publications drift across many surfaces — Scholar profiles, ORCID,
group websites, the chair website, paper README files. None of them is
authoritative; all of them go stale. The fix we want is one thing:

- **One BibTeX file in version control** (`slds.bib`) is the SSOT.
- Everything that needs SLDS publications (websites, member pages, reports,
  rendered HTML — all to come later) is generated *from* it.
- The job of `publs` is the boring, error-prone middle step: keeping the
  SSOT current without silently corrupting it, by surfacing candidate
  entries from external databases and letting a human accept or reject
  each one.

## What the tool does (and does not)

The tool **does**:

- query external publication sources for each SLDS member,
- match each returned record against `slds.bib` (DOI first, then normalized
  title) and report which records are *missing*,
- in interactive review mode: render each missing candidate, fetch a
  publisher BibTeX entry via `doi.org` content negotiation (with a
  synthesized fallback when no DOI exists), and *append* accepted entries
  to `slds.bib`.

The tool **does not**:

- ever rewrite, reformat, or delete existing `slds.bib` entries,
- merge or deduplicate inside the SSOT,
- decide for you which candidate to keep — `slds.bib` is the trust boundary;
  every entry that lands there has been seen by a human first.

## Source priority (and why)

Sources are queried in priority order, configured in `config.yaml`:

1. **OpenAlex** — *implemented.* Generous, reliable, parsed JSON. Ships
   DOIs for most journal/conference papers, plus author IDs (which is
   how we avoid name-collision false matches if you fill them in).
2. **Crossref** — *not yet implemented.* DOI-centric; useful as a
   second-pass verifier and for funder/affiliation queries.
3. **Google Scholar** — *not yet implemented, deliberately last.* Has the
   broadest coverage (theses, talks, unindexed venues) but blocks
   automated access aggressively. Will live behind an explicit
   `--source scholar` flag so it never fires by default.

## Install

```bash
cd publs
uv sync
```

## Configure

### `config.yaml`

| key                | meaning                                                   |
|--------------------|-----------------------------------------------------------|
| `ssot_path`        | path to the SSOT (default `slds.bib`)                     |
| `min_year`         | drop candidates older than this; `null` = keep all        |
| `mailto`           | contact email for OpenAlex's polite pool (recommended)    |
| `enabled_sources`  | sources to query, in priority order                       |

### `members.yaml`

One row per SLDS member. ID resolution order, most reliable first:

1. `openalex_id` — e.g. `A5093022032` (the trailing token of the OpenAlex
   author URL `https://openalex.org/A5093022032`). No API call needed and
   no chance of confusing two people with the same name.
2. `orcid` — `0000-0000-0000-0000`. OpenAlex resolves this to an author ID
   in one call.
3. *name search* — last resort. The tool warns and logs the top 3 OpenAlex
   hits.

`scholar_id` is preserved for the future Scholar integration. `include:
false` skips a row without removing it (alumni, admins).

#### Why filling in `openalex_id` matters (a lot)

Name search is fine for an unambiguous name (e.g. *Fiona Katharina Ewald*).
It is **wrong** for common names. As a real example from this repo's first
end-to-end check:

```
  Andreas Bender              351 candidates   343 missing
  Sebastian Fischer           248 candidates   248 missing
  Yawei Li                    246 candidates   246 missing
  Florian Karl                141 candidates   141 missing
  Chris Kolb                   45 candidates    45 missing
  ...
```

Those numbers make no sense for SLDS members. They show a different
person — usually the most-cited researcher with that exact name — being
returned by OpenAlex's name search. The tool can't tell the difference
without an explicit ID, so it dutifully reports "343 papers you don't
have" and the noise drowns out everything else.

A 100% missing rate combined with a high candidate count is the
fingerprint. When you see it: open the SLDS member's actual OpenAlex
profile (or follow a paper of theirs through OpenAlex's search), copy the
`A...` author ID into `members.yaml`, and re-run `publs check`. The number
should drop into single or low-double digits.

## The update workflow

Day-to-day, the loop is:

```bash
# 0. Make sure slds.bib is committed and clean. publs only appends, but
#    review-and-commit is the discipline that keeps the SSOT trustworthy.
git status

# 1. (One-time per member) verify which IDs they have configured.
uv run publs members

# 2. Read-only sanity check. Lists candidates per member, and how many
#    of those candidates aren't already in slds.bib. Costs zero writes.
#    Use this to spot wrong-author misfires before doing any review.
uv run publs check

# 3. Interactive review for one member at a time. Easier to stay focused
#    than reviewing everyone at once.
uv run publs review --source openalex --member bischl

# 4. Inspect the diff and commit. Each accepted entry is one append, so
#    the diff is a stack of new @article{...} blocks at the end.
git diff slds.bib
git add slds.bib && git commit -m "slds.bib: + 7 entries (Bischl, OpenAlex)"
```

For each missing candidate, `review` prints title / authors / year / venue
/ DOI / source ID and prompts:

```
[a]ccept / [r]eject / [s]kip / [q]uit
```

- **accept** — try `doi.org` for publisher BibTeX (content-negotiated
  `application/x-bibtex`); fall back to a synthesized entry from OpenAlex
  JSON if doi.org doesn't cooperate. Append to `slds.bib` immediately
  with `fsync`. Citation-key collisions get a `-2`/`-3`/... suffix, never
  silent overwrite.
- **reject** — silent in the current cut. The candidate will resurface
  on the next run; the SSOT being in git means rejections have a
  perfectly good place to live (your fingertips). A persistent rejection
  list is on the roadmap if reruns get tedious.
- **skip** / **quit** — what they say. Quitting stops the multi-member
  loop; entries already accepted are already on disk.

## Matching: how a candidate becomes "present" or "missing"

For each Candidate from a source, in order:

1. **DOI match** — normalize (strip `https://doi.org/` etc., lowercase),
   look it up in the SSOT's DOI index. Definitive when both sides have a
   DOI. Note that the SSOT in this repo only has DOIs on roughly 20% of
   entries — most matches will go to step 2.
2. **Normalized-title match** — strip TeX braces / punctuation, collapse
   whitespace (including non-breaking space, which OpenAlex emits inside
   titles), lowercase. Look up in the SSOT's title index.
3. Otherwise **missing** — surfaced to `check` and `review`.

The matcher is intentionally conservative: a real duplicate that slips
through and gets re-prompted is cheap (you press `r`); a false positive
that suppresses a genuinely missing paper is expensive (you never see
it). When in doubt the tool errs toward surfacing the candidate.

## Editing the SSOT by hand

`slds.bib` is a regular BibTeX file. Edit it directly: fix typos, normalize
keys, add `tag={nlp}` style fields, drop entries that shouldn't be in the
group bibliography. `publs` re-reads the file from disk on every run, so
nothing in the tool will fight you.

The append path preserves whatever shape the file already has — no
reformatting, no key reordering, no whitespace changes. The only mutation
`publs` performs is "append a new `@type{key, ...}` block to the end."

## Module layout

```
src/publs/
  cli.py            click commands: members / check / review
  config.py         Settings, Member, MemberList (YAML loaders)
  bibdb.py          load slds.bib, build DOI/title indices, atomic append
  models.py         shared Candidate dataclass
  match.py          Candidate -> "present" / "missing" against BibDB
  review.py         interactive loop, BibTeX building, key-collision handling
  sources/
    openalex.py     resolve author ID, page works, normalize to Candidate
                    (fetch_bibtex_for_doi + build_bibtex_from_candidate)
    # crossref.py   future
    # scholar.py    future
```

## Roadmap

- **Crossref source** — second-pass enrichment for entries with skeletal
  metadata, plus discovery via funder / affiliation queries OpenAlex
  misses.
- **Scholar source** — last-resort discovery for things neither OpenAlex
  nor Crossref index. Behind `--source scholar`.
- **Persistent rejection list** — keyed by DOI / normalized title so
  rejected candidates don't re-prompt every run.
- **Linting** — `publs lint slds.bib` to flag duplicate keys, suspicious
  venues, missing DOIs on entries that should have them, malformed URL
  fields (the existing SSOT has plenty of `<br><a href=...>link</a>` in
  `url=` that will not survive any sane downstream renderer).
- **Web/render targets** — the actual point of the SSOT: per-member,
  per-year, per-tag HTML/Markdown views generated *from* `slds.bib`.
