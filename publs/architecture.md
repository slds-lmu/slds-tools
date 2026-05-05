# architecture

## In principle

```
  members.yaml ─┐                                              ┌─► append    (new)
                ├─► source ─► Candidate ─► match ─► review ─►  ┤
  config.yaml ──┘  (openalex)  (normalized)  (vs SSOT)  (a/r/s/q)  └─► replace   (fix)
                                                                  └─► leave alone
```

One file (`slds.bib`) is the source of truth. The tool mutates it in two
ways, both human-approved at review time: **append** a new entry, or
**replace** an existing entry whose metadata diverges from a more
authoritative source.

## Robustness, by mechanism

- **The SSOT is never auto-rewritten wholesale.** No reformat, no dedupe,
  no key reorder. Mutations are *per entry*: append a new block at end,
  or replace exactly one existing block in place. Hand-edits and tool
  edits coexist because the tool re-reads from disk on every run.
- **Writes are atomic.** Append is one `open(a) + fsync` of a single
  `@entry{...}` block. Replace is tmpfile + `os.replace`. Ctrl-C,
  network drop, or CAPTCHA halfway through a session never corrupts
  the file.
- **Replacements are diff-confirmed.** A "fix" candidate is shown as a
  unified diff of old vs proposed entry; user accepts the whole block
  or rejects. No silent partial-field merges.
- **Matching errs toward surfacing, not suppressing.** DOI match first
  (definitive); normalized-title match second. Outcome: `missing` (→
  append) / `divergent` (→ replace, after diff) / `matching` (→ leave
  alone). A duplicate that slips through costs one keystroke (`r`); a
  false-positive that silently hides a real paper costs forever.
- **Author identity is anchored, not searched.** Each source has one
  per-member ID in `members.yaml` (`openalex_id`, `orcid`,
  `scholar_id`). All optional; a null ID silently skips that member
  on that source. There is no name search anywhere — the class of bug
  where the tool returns *some other* researcher's papers cannot
  occur. Coverage gaps are made visible by a loud end-of-run warning,
  not by failures.
- **Sources are fail-safe to most-fragile.** OpenAlex (parsed JSON) →
  Crossref (DOI-centric) → Scholar (last; blocks easily). The default
  path uses only the robust sources; Scholar fires only when explicitly
  requested.
- **Key collisions are renamed, never overwritten.** If a new entry's
  citation key already exists in the SSOT, it gets a `-2`/`-3`/...
  suffix at append time.
- **Read-only mode exists.** `publs check` does the full pipeline up to
  but not including append. Use it to validate `members.yaml` and
  source health before any review session.
- **The trust boundary is the human.** Every entry that lands in
  `slds.bib` was seen on screen and accepted with a keystroke. The
  worst-case failure of any source is "noisier review queue", not
  "corrupted SSOT".
