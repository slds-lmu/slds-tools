"""Google Scholar scraping + on-disk JSON cache.

Two responsibilities:

1. Translate `scholarly` API objects into our Publication / MemberCache
   dataclasses (which control the on-disk schema).
2. Implement the cache layer so re-runs are cheap and a partial network
   failure doesn't lose previously fetched members.

The cache schema is intentionally simple JSON (one file per member, keyed by
slug) so it can be inspected and edited by hand if needed.
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

    `bibtex` is None when fetched with `--no-bibtex`; the renderer will then
    silently skip the entry. `citation_id` is scholarly's `author_pub_id`,
    kept so we could re-fetch a single pub later if needed.
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
    back to compare against `cache_ttl_days`.
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


# Module-level guard so `configure_proxy` is a no-op on the second call. The
# `scholarly` library installs the proxy generator globally, so calling it
# twice in the same process would re-do the (slow) FreeProxies discovery.
_PROXY_CONFIGURED = False


def configure_proxy(strategy: str) -> None:
    """Configure scholarly's HTTP layer. Call once per process.

    Strategies:
      - "none": direct requests. Will rate-limit on big runs; combine with
        `--no-bibtex` and the cache for safer first runs.
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

    `ttl_days <= 0` disables freshness — every run will refetch. Used by
    `fetch_all` to decide whether to skip a member.
    """
    if ttl_days <= 0 or not path.exists():
        return False
    raw = json.loads(path.read_text())
    fetched_at = datetime.fromisoformat(raw["fetched_at"])
    age = datetime.now(timezone.utc) - fetched_at
    return age < timedelta(days=ttl_days)


def fetch_member(member: Member, with_bibtex: bool = True) -> MemberCache:
    """Fetch all publications for a single member from Google Scholar.

    Two-stage scrape via `scholarly`:
      1. `search_author_id` + `fill(..., ["publications"])` — one request,
         returns the full publication list with titles/years/authors.
      2. Optional `scholarly.bibtex(pub)` per publication — one extra
         request each, much more aggressively rate-limited. Disable with
         `with_bibtex=False` for fast incremental scrapes.

    Failures of (2) for a single pub are logged and that pub's `bibtex`
    stays None; the renderer will then skip it.

    Raises ValueError if the member has no scholar_id.
    """
    if not member.scholar_id:
        raise ValueError(f"Member {member.name!r} has no scholar_id.")

    log.info("Looking up %s (id=%s)", member.name, member.scholar_id)
    author = scholarly.search_author_id(member.scholar_id)
    author = scholarly.fill(author, sections=["publications"])

    pubs: list[Publication] = []
    for i, raw_pub in enumerate(author.get("publications", []), start=1):
        bib = raw_pub.get("bib", {})
        title = bib.get("title", "")
        # `pub_year` is a string in scholarly's output; coerce defensively
        # because some entries (preprints, theses) have non-numeric years.
        year_raw = bib.get("pub_year")
        try:
            year = int(year_raw) if year_raw else None
        except (TypeError, ValueError):
            year = None

        bibtex_str = None
        if with_bibtex:
            try:
                bibtex_str = scholarly.bibtex(raw_pub)
            except Exception as e:  # noqa: BLE001 — scholarly raises various
                # One bad pub shouldn't tank the whole member; record None
                # and move on. The renderer will quietly drop it.
                log.warning("BibTeX fetch failed for %r: %s", title, e)

        pubs.append(Publication(
            title=title,
            year=year,
            authors=bib.get("author", ""),
            venue=bib.get("citation", ""),
            citation_id=raw_pub.get("author_pub_id", ""),
            bibtex=bibtex_str,
        ))
        # Progress log every 10 pubs — useful for prolific authors (337+).
        if i % 10 == 0:
            log.info("  ... %d publications fetched", i)

    return MemberCache(
        scholar_id=member.scholar_id,
        name=member.name,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        publications=pubs,
    )


def fetch_all(
    settings: Settings,
    members: list[Member],
    *,
    force: bool = False,
    with_bibtex: bool = True,
) -> dict[str, MemberCache | None]:
    """Fetch many members, respecting cache TTL and inter-member delays.

    Behavior per member:
      - missing scholar_id      -> warn, record None, continue
      - cache fresh (and not force) -> load from disk, no network
      - otherwise               -> live fetch, write JSON cache, sleep

    Returns a dict keyed by member name. None values mean "skipped or
    failed" — the caller can introspect to print a summary if desired.

    Network failures on individual members are logged and recorded as None
    rather than raised, so a Scholar block on member #5 doesn't lose the
    successful fetches for members #1–#4 (they were already written to
    disk).
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
        if not force and is_cache_fresh(path, settings.cache_ttl_days):
            log.info("Cache fresh for %s; skipping (use --force to refetch).", member.name)
            results[member.name] = MemberCache.from_file(path)
            continue

        try:
            cache = fetch_member(member, with_bibtex=with_bibtex)
        except Exception as e:  # noqa: BLE001 — keep going on per-member failures
            log.error("Failed to fetch %s: %s", member.name, e)
            results[member.name] = None
            continue

        # Write immediately so a crash on member N+1 doesn't lose member N.
        path.write_text(cache.to_json())
        results[member.name] = cache
        log.info("Wrote %s (%d pubs)", path, len(cache.publications))

        # Politeness delay — but skip after the last member so `--member`
        # runs aren't artificially slow.
        if i < len(members) - 1 and settings.delay_between_members > 0:
            time.sleep(settings.delay_between_members)

    return results
