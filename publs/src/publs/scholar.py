"""Google Scholar scraping + on-disk JSON cache.

Two responsibilities:

1. Translate `scholarly` API objects into our Publication / MemberCache
   dataclasses (which control the on-disk schema).
2. Implement the cache layer so re-runs are cheap and a partial network
   failure doesn't lose previously fetched members.

The cache schema is intentionally simple JSON (one file per member, keyed by
slug) so it can be inspected and edited by hand if needed.

BibTeX fetching uses the "search-then-cite" path because scholarly's
`bibtex()` is broken for AUTHOR_PUBLICATION_ENTRY (the cite popup is loaded
via JavaScript on author profiles, so the URL isn't in the HTML). We instead
search Scholar by title, take the first PUBLICATION_SEARCH_SNIPPET, and call
`scholarly.bibtex` on that — costs one extra request per pub but produces
real BibTeX with full author names, journal, volume, pages, etc.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scholarly import ProxyGenerator, scholarly

from .config import Member, Settings

log = logging.getLogger(__name__)


@dataclass
class Publication:
    """One publication as stored in the JSON cache.

    `bibtex` is None when not yet fetched (or when search-then-cite failed
    for this title); the renderer skips entries with None. `citation_id` is
    scholarly's `author_pub_id`, kept for traceability and as the dedup key
    inside a member's cache.
    """

    title: str
    year: int | None
    authors: str
    venue: str
    citation_id: str
    bibtex: str | None


@dataclass
class MemberCache:
    """All scraped data for one SLDS member.

    `fetched_at` is an ISO-8601 UTC timestamp; `is_cache_fresh` parses it
    back to compare against `cache_ttl_days`. Updated whenever the cache is
    rewritten (i.e. after every per-pub bibtex fetch in incremental mode).
    """

    scholar_id: str
    name: str
    fetched_at: str
    publications: list[Publication]

    def to_json(self) -> str:
        """Serialize to pretty-printed JSON (UTF-8 preserved for umlauts)."""
        return json.dumps(
            {
                "scholar_id": self.scholar_id,
                "name": self.name,
                "fetched_at": self.fetched_at,
                "publications": [asdict(p) for p in self.publications],
            },
            indent=2,
            ensure_ascii=False,
        )

    @classmethod
    def from_file(cls, path: Path) -> "MemberCache":
        """Load a previously written cache file."""
        raw = json.loads(path.read_text())
        return cls(
            scholar_id=raw["scholar_id"],
            name=raw["name"],
            fetched_at=raw["fetched_at"],
            publications=[Publication(**p) for p in raw["publications"]],
        )

    def write(self, path: Path) -> None:
        """Update `fetched_at` and write atomically.

        Atomic via tmpfile + rename so a crash mid-write can't leave a
        truncated JSON file that breaks the next resume.
        """
        self.fetched_at = datetime.now(timezone.utc).isoformat()
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(self.to_json())
        tmp.replace(path)


# Module-level guard so `configure_proxy` is a no-op on the second call. The
# `scholarly` library installs the proxy generator globally, so calling it
# twice in the same process would re-do the (slow) FreeProxies discovery.
_PROXY_CONFIGURED = False


def configure_proxy(strategy: str) -> None:
    """Configure scholarly's HTTP layer. Call once per process.

    Strategies:
      - "none": direct requests. Will rate-limit on big runs; combine with
        per-pub delays + the resumable cache to chip away in chunks.
      - "free": scholarly's FreeProxies pool. Currently broken upstream
        (scholarly 1.7.11 calls `httpx.Client(proxies=...)` which httpx 0.28
        removed), so we catch the failure and fall back to direct requests.

    Idempotent — subsequent calls within the same process are no-ops.
    """
    global _PROXY_CONFIGURED
    if _PROXY_CONFIGURED:
        return
    if strategy == "none":
        log.info("No proxy configured; using direct requests.")
    elif strategy == "free":
        log.info("Configuring scholarly FreeProxies (may take a moment)...")
        pg = ProxyGenerator()
        try:
            ok = pg.FreeProxies()
        except Exception as e:  # noqa: BLE001 — scholarly+httpx version drift
            # Don't let an upstream regression abort the whole run; the user
            # already gets warned about rate limits in the docs.
            log.warning("FreeProxies failed (%s); falling back to direct requests.", e)
            ok = False
        if ok:
            scholarly.use_proxy(pg)
    else:
        raise ValueError(f"Unknown proxy strategy: {strategy!r}")
    _PROXY_CONFIGURED = True


def cache_path(settings: Settings, member: Member) -> Path:
    """Return the on-disk JSON cache path for a given member."""
    return settings.cache_dir / f"{member.slug(settings.filename_style)}.json"


def is_cache_fresh(path: Path, ttl_days: int) -> bool:
    """True iff the cache exists and is younger than `ttl_days` days.

    `ttl_days <= 0` disables freshness — every run will refetch. Note that
    "fresh" doesn't mean "complete" — a cache can be fresh with most pubs
    still missing BibTeX (because the previous run got rate-limited). The
    fetch loop separately checks per-pub completeness for resume.
    """
    if ttl_days <= 0 or not path.exists():
        return False
    raw = json.loads(path.read_text())
    fetched_at = datetime.fromisoformat(raw["fetched_at"])
    age = datetime.now(timezone.utc) - fetched_at
    return age < timedelta(days=ttl_days)


def fetch_pub_bibtex(title: str) -> str | None:
    """Get a real BibTeX entry for one publication via search-then-cite.

    Two Scholar requests:
      1. `search_single_pub(title)` — returns the first matching
         PUBLICATION_SEARCH_SNIPPET (which carries `url_scholarbib`).
      2. `scholarly.bibtex(snippet)` — fetches the cite popup and parses
         out the real BibTeX with full author names, journal, volume, etc.

    Returns None on any failure (no match, malformed result, network
    error). The caller logs and moves on; one bad title shouldn't block the
    whole member.

    Note that title-search can match the wrong paper for very common
    titles. We don't currently verify the match; if you see weird entries
    in the .bib output, that's where to look.
    """
    try:
        snippet = scholarly.search_single_pub(title)
    except Exception as e:  # noqa: BLE001
        log.warning("Search failed for %r: %s", title, e)
        return None
    if not snippet or "bib" not in snippet:
        log.warning("No search match for %r", title)
        return None
    try:
        return scholarly.bibtex(snippet)
    except Exception as e:  # noqa: BLE001
        log.warning("BibTeX fetch failed for %r: %s", title, e)
        return None


def _listing_for_member(member: Member) -> list[Publication]:
    """Phase 1 of fetch_member: get the publication list (one Scholar request).

    Returns Publications with `bibtex=None` for all entries — phase 2 fills
    them in. Year coercion is defensive because some entries (preprints,
    theses) have non-numeric years in scholarly's output.
    """
    log.info("Looking up %s (id=%s)", member.name, member.scholar_id)
    author = scholarly.search_author_id(member.scholar_id)
    author = scholarly.fill(author, sections=["publications"])

    pubs: list[Publication] = []
    for raw_pub in author.get("publications", []):
        bib = raw_pub.get("bib", {})
        year_raw = bib.get("pub_year")
        try:
            year = int(year_raw) if year_raw else None
        except (TypeError, ValueError):
            year = None
        pubs.append(Publication(
            title=bib.get("title", ""),
            year=year,
            authors=bib.get("author", ""),
            venue=bib.get("citation", ""),
            citation_id=raw_pub.get("author_pub_id", ""),
            bibtex=None,
        ))
    return pubs


def fetch_member(
    settings: Settings,
    member: Member,
    *,
    force: bool = False,
    with_bibtex: bool = True,
) -> MemberCache:
    """Fetch one member with incremental cache writes and per-pub resume.

    Behavior:
      - If a cache exists and `force=False`, reuse the publication list from
        it; otherwise fetch the listing fresh from Scholar.
      - Iterate publications. For each one without `bibtex` set (and inside
        the year filter — see `min_year`), call `fetch_pub_bibtex` and write
        the cache to disk after every successful pub. A crash or rate-limit
        loses at most one in-flight pub.
      - Skip pubs whose year is below `settings.min_year` — the renderer
        would drop them anyway, so spending Scholar requests on them is
        wasted budget.
      - Sleep `delay_between_pubs` between BibTeX fetches.

    `with_bibtex=False` skips phase 2 entirely (just writes the listing).
    Useful for fast bootstrap or when you only want titles/years.

    Raises ValueError if the member has no scholar_id.
    """
    if not member.scholar_id:
        raise ValueError(f"Member {member.name!r} has no scholar_id.")

    path = cache_path(settings, member)

    # Load existing cache to resume; only refuse if --force was passed.
    if path.exists() and not force:
        cache = MemberCache.from_file(path)
        log.info("Resuming %s from cache (%d pubs, %d already with bibtex).",
                 member.name, len(cache.publications),
                 sum(1 for p in cache.publications if p.bibtex))
    else:
        pubs = _listing_for_member(member)
        cache = MemberCache(
            scholar_id=member.scholar_id,
            name=member.name,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            publications=pubs,
        )
        # Write the listing immediately so phase 2 can resume even if it
        # crashes on the very first BibTeX fetch.
        cache.write(path)
        log.info("Wrote listing for %s (%d pubs).", member.name, len(pubs))

    if not with_bibtex:
        return cache

    # Phase 2: per-pub BibTeX. Skip pubs that already have it (resume) and
    # pubs below min_year (would be filtered out at render anyway).
    todo = [
        (i, p) for i, p in enumerate(cache.publications)
        if p.bibtex is None
        and (settings.min_year is None or (p.year is not None and p.year >= settings.min_year))
    ]
    log.info("Need BibTeX for %d/%d pubs (others already filled or below min_year=%s).",
             len(todo), len(cache.publications), settings.min_year)

    for n, (i, pub) in enumerate(todo, start=1):
        bib = fetch_pub_bibtex(pub.title)
        if bib is not None:
            # Mutate in place + rewrite cache. Atomic write means a crash
            # here can't corrupt the cache, only the in-flight pub is lost.
            cache.publications[i].bibtex = bib
            cache.write(path)
        # Progress every 10 pubs so you can see the run is alive.
        if n % 10 == 0:
            log.info("  ... %d/%d bibtex fetched", n, len(todo))
        # Polite delay even on failure — rate-limit detection isn't binary,
        # backing off after a "no match" is still a good citizen.
        if n < len(todo) and settings.delay_between_pubs > 0:
            time.sleep(settings.delay_between_pubs)

    return cache


def fetch_all(
    settings: Settings,
    members: list[Member],
    *,
    force: bool = False,
    with_bibtex: bool = True,
) -> dict[str, MemberCache | None]:
    """Fetch many members, with cache TTL skipping and inter-member delays.

    Behavior per member:
      - missing scholar_id          -> warn, record None, continue
      - cache fresh AND complete    -> reuse, no network (see is_cache_fresh)
      - cache fresh but incomplete  -> resume per-pub fetch
      - otherwise                   -> live fetch from scratch

    Returns a dict keyed by member name. None values mean "skipped or
    failed" — caller can introspect to print a summary if desired.

    Network failures on individual members are logged and recorded as None
    rather than raised, so a Scholar block on member #5 doesn't lose the
    successful fetches for members #1–#4 (they were already written to
    disk by the per-pub incremental writer).
    """
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    # Skip the (potentially slow) FreeProxies setup if there's nothing to
    # fetch — happens when every member has scholar_id: null.
    if any(m.scholar_id for m in members):
        configure_proxy(settings.proxy)

    results: dict[str, MemberCache | None] = {}
    for i, member in enumerate(members):
        if not member.scholar_id:
            log.warning("Skipping %s: no scholar_id set in members.yaml.", member.name)
            results[member.name] = None
            continue

        path = cache_path(settings, member)
        # If cache is fresh AND every pub has bibtex (or is below min_year),
        # there's nothing to do — skip without touching the network.
        if not force and is_cache_fresh(path, settings.cache_ttl_days):
            cached = MemberCache.from_file(path)
            missing = sum(
                1 for p in cached.publications
                if p.bibtex is None
                and (settings.min_year is None or (p.year is not None and p.year >= settings.min_year))
            )
            if missing == 0 or not with_bibtex:
                log.info("Cache fresh and complete for %s; skipping.", member.name)
                results[member.name] = cached
                continue
            log.info("Cache fresh for %s but %d pubs still need bibtex; resuming.",
                     member.name, missing)

        try:
            cache = fetch_member(settings, member, force=force, with_bibtex=with_bibtex)
        except Exception as e:  # noqa: BLE001 — keep going on per-member failures
            log.error("Failed to fetch %s: %s", member.name, e)
            results[member.name] = None
            continue

        results[member.name] = cache
        log.info("Done %s (%d pubs, %d with bibtex).",
                 member.name, len(cache.publications),
                 sum(1 for p in cache.publications if p.bibtex))

        # Politeness delay — but skip after the last member so `--member`
        # runs aren't artificially slow.
        if i < len(members) - 1 and settings.delay_between_members > 0:
            time.sleep(settings.delay_between_members)

    return results
