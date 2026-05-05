"""External publication sources.

Each module in this package exposes a `fetch(member, settings)` function
returning a list of `Candidate` records (defined in `..models`). They are
queried in priority order configured via `enabled_sources`:

    1. openalex  -- generous, reliable, parsed JSON with DOIs
    2. crossref  -- DOI-centric enrichment (not yet implemented)
    3. scholar   -- last resort, blocks easily (not yet implemented)
"""
