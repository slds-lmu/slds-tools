# publs

Scrape SLDS member publications from Google Scholar into one BibTeX file per
member. Configurable via two YAML files; cached so repeated runs are cheap.

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
     scholar_id: s34vdQcAAAAJ        # <-- the value of `user=` in their profile URL
   ```

   Members with `scholar_id: null` are skipped with a warning. Set
   `include: false` to hide a member without removing the entry.

2. **`config.yaml`** — global knobs:
   - `min_year` — drop older publications (`null` = keep all)
   - `cache_ttl_days` — how long a cached fetch is considered fresh
   - `proxy` — `free` (scholarly's FreeProxies) or `none`
   - `delay_between_members` — politeness delay in seconds

## Use

```bash
# 1. List members and which have Scholar IDs configured.
uv run publs list

# 2. Pull from Google Scholar into cache/  (slow; rate-limited by Scholar)
uv run publs fetch
uv run publs fetch --member bischl       # single person
uv run publs fetch --force                # ignore cache TTL
uv run publs fetch --no-bibtex            # skip per-pub BibTeX (much faster)

# 3. Render cache/ into out/<lastname-firstname>.bib
uv run publs render
uv run publs render --member bischl
```

`fetch` and `render` are decoupled: change `min_year` or other render-only
settings and re-run `render` without re-hitting Scholar.

## Output

```
out/
  bischl-bernd.bib
  bothmann-ludwig.bib
  ...
```

Each file is a normal BibTeX file you can `\bibliography{out/bischl-bernd}` or
`\input` into your TeX project.

## Notes

- Google Scholar aggressively rate-limits scrapers. The default `proxy: free`
  uses scholarly's FreeProxies pool (works most of the time but is flaky); the
  cache means you usually only pay this cost once.
- `--no-bibtex` is much faster but produces no BibTeX in the cache, so `render`
  will emit nothing for those entries.
