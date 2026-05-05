# Architecture

## Short summary

A tool that maintains the BibTeX file for the SLDS research group. It surfaces
update suggestions from external sources when new publications appear, or when
existing entries are outdated, incorrect, or only partial.

Sources: OpenAlex, Crossref, Google Scholar.

```
  members.yaml ─┐                                              ┌─► append    (new)
                ├─► source ─► Candidate ─► match ─► review ─►  ┤
  config.yaml ──┘  (openalex)  (normalized)  (vs SSOT)  (a/r/s/q)  └─► replace   (fix)
                                                                  └─► leave alone
```

## General rules

- **`slds.bib` is the source of truth.** The tool mutates it in two ways, both human-approved at review time: **append** a new entry, or **replace** an existing entry whose metadata diverges from a more authoritative source.
- **Author identity is anchored, not searched.** Per-member platform IDs in `members.yaml`. A null ID skips that source for that member, and the tool warns about null IDs at the end of a run.
- **Writes are atomic.** Append is one `open(a) + fsync` of a single `@entry{...}` block. Replace is tmpfile + `os.replace`. Ctrl-C, network drop, or CAPTCHA halfway through a session never corrupts the file.
- **Replacements are diff-confirmed.** A "fix" candidate is shown as a unified diff of old vs proposed entry; user accepts the whole block or rejects. No silent partial-field merges.
- **Replacements preserve the citation key.** When the user accepts a fix, the proposed entry's key is rewritten to the existing SSOT key before splicing, so external documents that cite the entry don't break.
- **"Outdated" is conservative.** A candidate is flagged as a fix only when it strictly *adds* non-empty fields (currently `doi`, `year`, `venue`) that are missing or empty in the SSOT entry. Pure mismatches (different DOI, different year) are not auto-flagged — they need human attention but auto-flagging would presume the candidate is right.
- **Key collisions are renamed, never overwritten.** If a new entry's citation key already exists in the SSOT, it gets a `-2`/`-3`/... suffix at append time.

## Where things live

- `members.yaml` — SSOT for member identities. Hand-curated.
- `slds.bib` — SSOT for publications. Hand-curated; tool appends only.
- `config.yaml` — `ssot_path`, `min_year`, `mailto`, `enabled_sources`.
- `src/publs/` — the package
