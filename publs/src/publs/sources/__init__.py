"""External publication sources.

Each module in this package exposes a `fetch(member, settings)` function
returning a list of `Candidate` records (defined in `..models`). The
CLI's `--source` flag picks which one runs; per-member skipping happens
when that source's ID is null in `members.yaml`.

Priority order (also the order to build them in):

    1. openalex  -- generous, reliable, parsed JSON with DOIs
    2. crossref  -- DOI-centric enrichment (not yet implemented)
    3. scholar   -- last resort, blocks easily (not yet implemented)
"""
