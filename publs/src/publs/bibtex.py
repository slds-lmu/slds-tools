"""Render the JSON cache into one .bib file per member.

Pure transformation: no network, no scholarly. Reads what `scholar.fetch_all`
wrote, applies the `min_year` filter from Settings, drops entries without a
BibTeX string, and writes a normal BibTeX file with a small comment header.

Decoupling render from fetch means changing `min_year` (or any future
render-time filter) is a sub-second re-run instead of another Scholar scrape.
"""
from __future__ import annotations

import logging
from pathlib import Path

from .config import Member, Settings
from .scholar import MemberCache, cache_path

log = logging.getLogger(__name__)


def render_member(settings: Settings, member: Member) -> Path | None:
    """Read this member's JSON cache, write a filtered .bib to output_dir.

    Returns the written path, or None if the member has no cache yet (i.e.
    `publs fetch` was never run for them) — the warning explains what to do.
    The .bib gets a small `%`-comment header recording provenance (Scholar
    ID, fetch timestamp, filter applied) so a stale .bib is easy to spot.
    """
    cpath = cache_path(settings, member)
    if not cpath.exists():
        log.warning("No cache for %s at %s; run `publs fetch` first.", member.name, cpath)
        return None

    cache = MemberCache.from_file(cpath)
    entries = _filter_and_format(cache, settings.min_year)

    settings.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = settings.output_dir / f"{member.slug(settings.filename_style)}.bib"
    header = (
        f"% Publications for {cache.name}\n"
        f"% Scholar ID: {cache.scholar_id}\n"
        f"% Fetched: {cache.fetched_at}\n"
        f"% Min year filter: {settings.min_year}\n\n"
    )
    # Trailing newline only when there were entries — keeps an empty .bib
    # tidy at exactly four header lines.
    out_path.write_text(header + "\n\n".join(entries) + ("\n" if entries else ""))
    log.info("Wrote %s (%d entries)", out_path, len(entries))
    return out_path


def render_all(settings: Settings, members: list[Member]) -> list[Path]:
    """Render every member; return the list of files actually written.

    Members without a cache file are skipped (with a warning from
    `render_member`) and excluded from the returned list, so callers can
    print an accurate count.
    """
    written: list[Path] = []
    for m in members:
        p = render_member(settings, m)
        if p is not None:
            written.append(p)
    return written


def _filter_and_format(cache: MemberCache, min_year: int | None) -> list[str]:
    """Apply year + bibtex-presence filters; return ready-to-join BibTeX strings.

    Two drop reasons:
      - year missing or below `min_year` (when `min_year` is set)
      - no BibTeX string in cache (i.e. fetched with `--no-bibtex` or the
        per-pub bibtex request failed at fetch time)
    """
    out: list[str] = []
    for pub in cache.publications:
        if min_year is not None and (pub.year is None or pub.year < min_year):
            continue
        if not pub.bibtex:
            log.debug("Skipping %r: no BibTeX in cache.", pub.title)
            continue
        out.append(pub.bibtex.strip())
    return out
