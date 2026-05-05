"""Interactive accept/reject loop for missing candidates.

For each candidate not yet in the SSOT, we render a one-screen summary
and prompt the user. Accepted entries are appended immediately, so a
Ctrl-C never loses the work already done. Rejections are silent — they
will resurface on the next `publs review` run, which is fine because
the SSOT is under version control and the user can grep for previously
considered DOIs.

Future: persistent rejection list keyed by DOI / normalized title, so
reruns don't re-prompt for things you've already turned down. Out of
scope for the first cut.
"""
from __future__ import annotations

import logging
import sys

import click

from .bibdb import BibDB
from .config import ID_FIELD_BY_SOURCE, Member, Settings
from .models import Candidate
from .sources import openalex

log = logging.getLogger(__name__)


def _render(cand: Candidate, member: Member) -> str:
    authors = ", ".join(cand.authors[:6]) + (
        f", ... (+{len(cand.authors) - 6})" if len(cand.authors) > 6 else ""
    )
    lines = [
        click.style(f"  {cand.title}", bold=True),
        f"    authors: {authors or '?'}",
        f"    year:    {cand.year or '?'}    venue: {cand.venue or '?'}",
        f"    type:    {cand.type or '?'}",
        f"    doi:     {cand.doi or '-'}",
        f"    url:     {cand.url or '-'}",
        f"    source:  {cand.source} ({cand.source_id})",
        f"    member:  {member.name}",
    ]
    return "\n".join(lines)


def _build_entry(cand: Candidate, settings: Settings) -> tuple[str, str]:
    """Return (bibtex_entry, source_label).

    Tries publisher BibTeX via doi.org first; falls back to a
    locally-built entry from the Candidate. The source_label is shown to
    the user so they know what flavor they're accepting.
    """
    if cand.doi:
        bib = openalex.fetch_bibtex_for_doi(cand.doi, settings)
        if bib:
            return bib, "doi.org publisher BibTeX"
        log.info("doi.org BibTeX unavailable; falling back to OpenAlex JSON")
    return openalex.build_bibtex_from_candidate(cand), "synthesized from OpenAlex"


def _extract_key(bibtex_entry: str) -> str:
    """Pull the citation key out of '@type{key, ...}'."""
    head, _, _ = bibtex_entry.partition(",")
    _, _, key = head.partition("{")
    return key.strip()


def review_member(member: Member, candidates: list[Candidate],
                  db: BibDB, settings: Settings) -> tuple[int, int, bool]:
    """Walk through `candidates` interactively.

    Returns (accepted, rejected, quit). On quit, the caller stops
    iterating to other members.
    """
    accepted = rejected = 0
    if not candidates:
        click.echo(f"  no missing entries for {member.name}")
        return 0, 0, False

    click.echo()
    click.echo(click.style(
        f"=== {member.name}: {len(candidates)} missing candidate(s) ===",
        fg="cyan",
    ))

    for i, cand in enumerate(candidates, start=1):
        click.echo()
        click.echo(f"[{i}/{len(candidates)}]")
        click.echo(_render(cand, member))
        while True:
            choice = click.prompt(
                "  [a]ccept / [r]eject / [s]kip / [q]uit",
                default="s", show_default=False,
            ).strip().lower()
            if choice in ("a", "accept"):
                bib, label = _build_entry(cand, settings)
                key = _extract_key(bib)
                # Avoid colliding with existing SSOT keys. If a duplicate is
                # detected, suffix with -2 etc. — better than silently
                # corrupting the bib by writing two entries with the same key.
                if db.has_key(key):
                    base = key
                    n = 2
                    while db.has_key(f"{base}-{n}"):
                        n += 1
                    new_key = f"{base}-{n}"
                    bib = bib.replace(f"{{{key},", f"{{{new_key},", 1)
                    log.warning("Key %s already in SSOT; renamed to %s",
                                key, new_key)
                    key = new_key
                db.append(bib, doi=cand.doi or None,
                          title=cand.title or None, key=key)
                click.echo(click.style(
                    f"  + appended @{key}  ({label})", fg="green",
                ))
                accepted += 1
                break
            if choice in ("r", "reject"):
                rejected += 1
                break
            if choice in ("s", "skip", ""):
                break
            if choice in ("q", "quit"):
                return accepted, rejected, True
            click.echo("  please answer a / r / s / q")

    return accepted, rejected, False


def review_all(members: list[Member], db: BibDB, settings: Settings,
               source: str) -> None:
    """Top-level driver: fetch from `source` per member, then review."""
    if source != "openalex":
        # crossref / scholar are stubs for now. Keep the surface obvious so
        # the CLI error is actionable instead of mysterious.
        click.echo(f"source {source!r} is not implemented yet", err=True)
        sys.exit(2)

    id_field = ID_FIELD_BY_SOURCE[source]
    total_accepted = total_rejected = 0
    for m in members:
        if not getattr(m, id_field):
            click.echo(f"\nskipping {m.name}: no {id_field}")
            continue
        click.echo(f"\nfetching from {source}: {m.name}")
        cands = openalex.fetch(m, settings)
        click.echo(f"  {len(cands)} works after min_year filter")
        from .match import split_missing
        missing = split_missing(cands, db)
        click.echo(f"  {len(missing)} missing from SSOT")
        a, r, q = review_member(m, missing, db, settings)
        total_accepted += a
        total_rejected += r
        if q:
            click.echo("\nquitting on user request.")
            break

    click.echo()
    click.echo(click.style(
        f"summary: +{total_accepted} accepted / -{total_rejected} rejected",
        fg="cyan",
    ))
    click.echo(f"SSOT now has {len(db)} entries: {db.path}")
