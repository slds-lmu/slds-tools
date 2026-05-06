"""Interactive accept/reject loops for missing and outdated candidates.

Two flows, both driven by `review_all`:

  - Append flow ("missing"):  for each candidate not yet in the SSOT,
    render a one-screen summary and prompt a/r/s/q. Accepts append
    immediately so a Ctrl-C never loses already-confirmed work.

  - Replace flow ("outdated"): for each candidate that matches an
    existing SSOT entry but adds metadata fields it lacks (e.g. a DOI
    that wasn't there before), render a unified diff of old-vs-proposed
    and prompt a/r/s/q. Accepts replace atomically (tmpfile + os.replace
    in BibDB), preserving the existing citation key so external
    references don't break.

Rejections are silent — they will resurface on the next run. The SSOT
is under version control, so a stray accept can always be reverted by
hand.
"""
from __future__ import annotations

import difflib
import logging
import sys

import click

from .bibdb import BibDB, add_fields
from .config import ID_FIELD_BY_SOURCE, Member, Settings
from .match import FieldFix
from .models import Candidate
from .sources import openalex

log = logging.getLogger(__name__)


def _render(cand: Candidate, member: Member) -> str:
    """One-screen text summary of a candidate for the append prompt."""
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


def _render_diff(old_text: str, new_text: str, key: str, label: str) -> str:
    """Color-render a unified diff of old vs proposed entry text.

    Caller strips trailing whitespace from both sides so the diff
    focuses on the entry block itself, not surrounding blank lines.
    `label` is the prompt-side description (e.g. "adds: doi, venue").
    """
    diff = difflib.unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        fromfile=f"slds.bib (current @{key})",
        tofile=f"proposed ({label})",
        lineterm="",
    )
    out: list[str] = []
    for line in diff:
        if line.startswith("+++") or line.startswith("---"):
            out.append(click.style(line, fg="white", bold=True))
        elif line.startswith("+"):
            out.append(click.style(line, fg="green"))
        elif line.startswith("-"):
            out.append(click.style(line, fg="red"))
        elif line.startswith("@@"):
            out.append(click.style(line, fg="cyan"))
        else:
            out.append(line)
    return "\n".join(out)


def review_member(member: Member, candidates: list[Candidate],
                  db: BibDB, settings: Settings) -> tuple[int, int, bool]:
    """Walk through `candidates` (append flow) interactively.

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
                    bib = BibDB._rekey(bib, new_key)
                    log.warning("Key %s already in SSOT; renamed to %s",
                                key, new_key)
                    key = new_key
                db.append(bib)
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


def review_outdated_member(
    member: Member,
    items: list[tuple[Candidate, str, tuple[FieldFix, ...]]],
    db: BibDB, settings: Settings,
) -> tuple[int, int, bool]:
    """Walk through outdated entries (additive replace flow) interactively.

    For each (Candidate, old_key, fixes) tuple, build the proposal by
    inserting the missing field(s) into the existing SSOT entry text —
    the citation key, entry type, all other fields, and the formatting
    are preserved verbatim. Render a unified diff (which therefore
    shows only added lines) and prompt a/r/s/q. Accept triggers an
    atomic in-place replace.

    Returns (accepted, rejected, quit) like review_member.
    """
    accepted = rejected = 0
    if not items:
        return 0, 0, False

    click.echo()
    click.echo(click.style(
        f"=== {member.name}: {len(items)} outdated entr{'y' if len(items) == 1 else 'ies'} ===",
        fg="magenta",
    ))

    for i, (cand, old_key, fixes) in enumerate(items, start=1):
        try:
            old_text = db.get_entry_text(old_key).rstrip()
        except KeyError:
            # The SSOT changed under us (concurrent edit, or an earlier
            # replace in this same run touched it). Skip gracefully.
            log.warning("entry @%s no longer in SSOT; skipping", old_key)
            continue

        additions = [(f.bib_name, f.value) for f in fixes]
        labels = ", ".join(f.label for f in fixes)
        new_block = add_fields(old_text, additions)

        click.echo()
        click.echo(f"[{i}/{len(items)}] @{old_key}")
        click.echo(_render_diff(old_text, new_block, old_key, f"adds: {labels}"))
        while True:
            choice = click.prompt(
                "  [a]ccept replace / [r]eject / [s]kip / [q]uit",
                default="s", show_default=False,
            ).strip().lower()
            if choice in ("a", "accept"):
                db.replace(old_key, new_block)
                click.echo(click.style(
                    f"  ~ replaced @{old_key}  (added: {labels})", fg="magenta",
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
    """Top-level driver: fetch from `source` per member, then review.

    Within each member, runs the append flow (missing candidates) first,
    then the replace flow (outdated candidates). 'q' at any prompt
    short-circuits the entire run.
    """
    if source != "openalex":
        # crossref / scholar are stubs for now. Keep the surface obvious
        # so the CLI error is actionable instead of mysterious.
        click.echo(f"source {source!r} is not implemented yet", err=True)
        sys.exit(2)

    id_field = ID_FIELD_BY_SOURCE[source]
    total_accepted = total_rejected = 0
    total_replaced = total_replaced_rejected = 0
    from .match import dedup_preprint_pairs, split_review_set

    for m in members:
        if not getattr(m, id_field):
            click.echo(f"\nskipping {m.name}: no {id_field}")
            continue
        click.echo(f"\nfetching from {source}: {m.name}")
        cands = openalex.fetch(m, settings)
        click.echo(f"  {len(cands)} works after min_year filter")
        cands, suppressed = dedup_preprint_pairs(cands)
        if suppressed:
            click.echo(f"  suppressed {len(suppressed)} preprint(s) "
                       f"with a published twin in this batch:")
            for s in suppressed:
                snippet = s.title[:70] + ("..." if len(s.title) > 70 else "")
                click.echo(f"    - [{s.year}] {snippet}")
        missing, outdated = split_review_set(cands, db)
        click.echo(f"  {len(missing)} missing / {len(outdated)} outdated")

        a, r, q = review_member(m, missing, db, settings)
        total_accepted += a
        total_rejected += r
        if q:
            click.echo("\nquitting on user request.")
            break

        a, r, q = review_outdated_member(m, outdated, db, settings)
        total_replaced += a
        total_replaced_rejected += r
        if q:
            click.echo("\nquitting on user request.")
            break

    click.echo()
    click.echo(click.style(
        f"summary: +{total_accepted} appended / -{total_rejected} rejected"
        f"  |  ~{total_replaced} replaced / -{total_replaced_rejected} rejected",
        fg="cyan",
    ))
    click.echo(f"SSOT now has {len(db)} entries: {db.path}")
