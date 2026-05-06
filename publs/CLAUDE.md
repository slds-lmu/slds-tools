# CLAUDE.md — publs

## Project in one line

Maintain `slds.bib` as the single source of truth for SLDS publications,
by surfacing candidates from external sources for human accept/reject.

## General
- Maintain a short, human-facing `architecture.md` that explains the general principles, and be aware of its contents.
- Use `PLAN.md` for your own internal planning and notes after communication with me. Maintain and clean it up yourself.


## Source priority
- Sources are listed in `architecture.md`; build code for them in that order (OpenAlex first, Google Scholar last).
- Really be careful so Google Scholar does not block us again.

## Document all config files and scripts
- (1) Header comment stating the purpose of the file;
- (2) for functions, doc purpose, inputs, outputs, side-effects;
- (3) in config files, doc the purpose of each option.

## Don't spread the same explanation across files
- Pick the single best home for a piece of doc
- Elsewhere, either be brief or use a one-line pointer 
- Redundant prose drifts out of sync and bloats


## BibTex handling

- The SSOT is never auto-rewritten wholesale.
- No heuristics that guess SSOT entry provenance; treat every BibTeX entry uniformly. 
  Do NOT branch on "looks hand-curated" vs "looks tool-generated".

