"""Click CLI for publs.

Three commands, all sharing `--config` / `--members` / `-v`:

    publs members             list configured members + which IDs they have
    publs check [--member X]  read-only: how many candidates are missing
    publs review --source openalex [--member X]
                              interactive: walk through missing candidates
                              and accept / reject each into slds.bib

`crossref` and `scholar` are accepted as `--source` values but currently
exit with an "unimplemented" error — they're staged for follow-up work.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from .bibdb import BibDB
from .config import ID_FIELD_BY_SOURCE, Member, MemberList, Settings
from .match import split_review_set
from .review import review_all
from .sources import openalex


def _warn_id_gaps(all_members: list[Member]) -> None:
    """Print a LOUD end-of-run summary of which platform IDs are missing.

    No name-search fallback exists; a missing ID just means that member
    is silently skipped on that platform. The warning is the only thing
    keeping the gap visible. We always run it across the full members
    list, not just the ones selected for this run, so the picture is
    complete regardless of `--member` filtering.
    """
    gaps: dict[str, list[str]] = {src: [] for src in ID_FIELD_BY_SOURCE}
    for m in all_members:
        if not m.include:
            continue
        for source, field_name in ID_FIELD_BY_SOURCE.items():
            if not getattr(m, field_name):
                gaps[source].append(m.name)

    if not any(gaps.values()):
        return

    bar = "*" * 72
    click.echo()
    click.echo(click.style(bar, fg="yellow", bold=True))
    click.echo(click.style(
        "WARNING: members.yaml has missing IDs. These members are SKIPPED",
        fg="yellow", bold=True,
    ))
    click.echo(click.style(
        "for the corresponding platform — the tool does NOT search by name.",
        fg="yellow", bold=True,
    ))
    click.echo(click.style(bar, fg="yellow", bold=True))
    for source, names in gaps.items():
        if not names:
            continue
        field_name = ID_FIELD_BY_SOURCE[source]
        click.echo(click.style(
            f"  {field_name:<13} ({source}): {len(names)} missing",
            fg="yellow", bold=True,
        ))
        for n in names:
            click.echo(click.style(f"      - {n}", fg="yellow"))
    click.echo(click.style(bar, fg="yellow", bold=True))
    click.echo(click.style(
        "Edit members.yaml to fill in IDs and widen coverage.",
        fg="yellow", bold=True,
    ))

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config.yaml"
DEFAULT_MEMBERS = Path(__file__).resolve().parents[2] / "members.yaml"


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


@click.group()
@click.option("--config", type=click.Path(exists=True, dir_okay=False, path_type=Path),
              default=DEFAULT_CONFIG, show_default=True)
@click.option("--members", "members_path",
              type=click.Path(exists=True, dir_okay=False, path_type=Path),
              default=DEFAULT_MEMBERS, show_default=True)
@click.option("-v", "--verbose", is_flag=True)
@click.pass_context
def main(ctx: click.Context, config: Path, members_path: Path, verbose: bool) -> None:
    """Maintain the SLDS BibTeX SSOT with suggestions from external sources."""
    _setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["settings"] = Settings.load(config)
    ctx.obj["members"] = MemberList.load(members_path)


@main.command(name="members")
@click.pass_context
def members_cmd(ctx: click.Context) -> None:
    """List configured members and which per-platform IDs they have."""
    # 3-column flag: OA OR GS, with '--' for missing.
    for m in ctx.obj["members"].members:
        oa = "OA" if m.openalex_id else "--"
        orc = "OR" if m.orcid       else "--"
        gs = "GS" if m.scholar_id  else "--"
        skip = " [skipped]" if not m.include else ""
        click.echo(f"  [{oa} {orc} {gs}]  {m.name}{skip}  ({m.role or '?'})")
    _warn_id_gaps(ctx.obj["members"].members)


@main.command()
@click.option("--member", "name", default=None, help="Only this member (substring match).")
@click.option("--source", "source",
              type=click.Choice(["openalex", "crossref", "scholar"]),
              default="openalex", show_default=True)
@click.pass_context
def check(ctx: click.Context, name: str | None, source: str) -> None:
    """Read-only: count how many candidates from `source` are missing from the SSOT."""
    if source != "openalex":
        raise click.ClickException(f"source {source!r} is not implemented yet")
    settings: Settings = ctx.obj["settings"]
    all_members = ctx.obj["members"].members
    members = ctx.obj["members"].select(name)
    if not members:
        raise click.ClickException(f"No members matched {name!r}.")
    try:
        db = BibDB.load(settings.ssot_path)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from None
    click.echo(f"SSOT: {settings.ssot_path} ({len(db)} entries)")
    click.echo()
    grand_total = grand_missing = grand_outdated = 0
    id_field = ID_FIELD_BY_SOURCE[source]
    for m in members:
        if not getattr(m, id_field):
            click.echo(f"  {m.name:<30}  -- skipped (no {id_field})")
            continue
        cands = openalex.fetch(m, settings)
        missing, outdated = split_review_set(cands, db)
        grand_total += len(cands)
        grand_missing += len(missing)
        grand_outdated += len(outdated)
        click.echo(f"  {m.name:<30}  {len(cands):>4} candidates  "
                   f"{len(missing):>4} missing  {len(outdated):>4} outdated")
    click.echo()
    click.echo(f"  {'TOTAL':<30}  {grand_total:>4} candidates  "
               f"{grand_missing:>4} missing  {grand_outdated:>4} outdated")
    _warn_id_gaps(all_members)


@main.command()
@click.option("--member", "name", default=None, help="Only this member (substring match).")
@click.option("--source", "source",
              type=click.Choice(["openalex", "crossref", "scholar"]),
              default="openalex", show_default=True)
@click.pass_context
def review(ctx: click.Context, name: str | None, source: str) -> None:
    """Interactive: walk through missing candidates and accept / reject."""
    settings: Settings = ctx.obj["settings"]
    all_members = ctx.obj["members"].members
    members = ctx.obj["members"].select(name)
    if not members:
        raise click.ClickException(f"No members matched {name!r}.")
    try:
        db = BibDB.load(settings.ssot_path)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from None
    click.echo(f"SSOT: {settings.ssot_path} ({len(db)} entries)")
    review_all(members, db, settings, source=source)
    _warn_id_gaps(all_members)


if __name__ == "__main__":
    main()
