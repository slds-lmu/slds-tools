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
from .config import MemberList, Settings
from .match import split_missing
from .review import review_all
from .sources import openalex

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
    """List configured members and which external IDs they have."""
    for m in ctx.obj["members"].members:
        ids = []
        if m.openalex_id: ids.append("OA")
        if m.orcid:       ids.append("OR")
        if m.scholar_id:  ids.append("GS")
        flag = ",".join(ids) if ids else "name-search"
        skip = " [skipped]" if not m.include else ""
        click.echo(f"  {flag:<14} {m.name}{skip}  ({m.role or '?'})")


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
    members = ctx.obj["members"].select(name)
    if not members:
        raise click.ClickException(f"No members matched {name!r}.")
    try:
        db = BibDB.load(settings.ssot_path)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from None
    click.echo(f"SSOT: {settings.ssot_path} ({len(db)} entries)")
    click.echo()
    grand_total = grand_missing = 0
    for m in members:
        cands = openalex.fetch(m, settings)
        missing = split_missing(cands, db)
        grand_total += len(cands)
        grand_missing += len(missing)
        click.echo(f"  {m.name:<30}  {len(cands):>4} candidates  "
                   f"{len(missing):>4} missing")
    click.echo()
    click.echo(f"  {'TOTAL':<30}  {grand_total:>4} candidates  "
               f"{grand_missing:>4} missing")


@main.command()
@click.option("--member", "name", default=None, help="Only this member (substring match).")
@click.option("--source", "source",
              type=click.Choice(["openalex", "crossref", "scholar"]),
              default="openalex", show_default=True)
@click.pass_context
def review(ctx: click.Context, name: str | None, source: str) -> None:
    """Interactive: walk through missing candidates and accept / reject."""
    settings: Settings = ctx.obj["settings"]
    members = ctx.obj["members"].select(name)
    if not members:
        raise click.ClickException(f"No members matched {name!r}.")
    try:
        db = BibDB.load(settings.ssot_path)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from None
    click.echo(f"SSOT: {settings.ssot_path} ({len(db)} entries)")
    review_all(members, db, settings, source=source)


if __name__ == "__main__":
    main()
