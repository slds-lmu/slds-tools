"""Click CLI for publs.

Three commands, all sharing `--config` / `--members` / `-v`:

    publs list                list members and which have a Scholar ID
    publs fetch [--member X]  hit Scholar, write JSON cache
    publs render [--member X] read cache, write .bib files

`fetch` and `render` are decoupled on purpose: changing `min_year` re-runs
in seconds without touching Scholar.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from .bibtex import render_all
from .config import MemberList, Settings
from .scholar import fetch_all

# Defaults point at the YAML files that ship next to the source tree (two
# levels up from this file: src/publs/cli.py -> repo root). Both flags accept
# absolute paths to override.
DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config.yaml"
DEFAULT_MEMBERS = Path(__file__).resolve().parents[2] / "members.yaml"


def _setup_logging(verbose: bool) -> None:
    """Configure root logging — INFO by default, DEBUG with `-v`."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        # stderr so logs don't pollute stdout (for piping `publs list` etc.)
        stream=sys.stderr,
    )


@click.group()
@click.option("--config", type=click.Path(exists=True, dir_okay=False, path_type=Path), default=DEFAULT_CONFIG, show_default=True)
@click.option("--members", "members_path", type=click.Path(exists=True, dir_okay=False, path_type=Path), default=DEFAULT_MEMBERS, show_default=True)
@click.option("-v", "--verbose", is_flag=True)
@click.pass_context
def main(ctx: click.Context, config: Path, members_path: Path, verbose: bool) -> None:
    """Scrape SLDS member publications from Google Scholar into BibTeX."""
    _setup_logging(verbose)
    # Load config + members once at the group level; subcommands pull from
    # ctx.obj so we don't re-parse the YAML on every command.
    ctx.ensure_object(dict)
    ctx.obj["settings"] = Settings.load(config)
    ctx.obj["members"] = MemberList.load(members_path)


@main.command()
@click.option("--member", "name", default=None, help="Only this member (substring match).")
@click.option("--force", is_flag=True, help="Refetch even if cache is fresh.")
@click.option("--no-bibtex", is_flag=True, help="Skip per-pub BibTeX fetch (much faster).")
@click.pass_context
def fetch(ctx: click.Context, name: str | None, force: bool, no_bibtex: bool) -> None:
    """Pull publications from Google Scholar into the JSON cache."""
    settings: Settings = ctx.obj["settings"]
    members = ctx.obj["members"].select(name)
    if not members:
        # Distinct exit so `--member typo` doesn't silently no-op.
        raise click.ClickException(f"No members matched {name!r}.")
    fetch_all(settings, members, force=force, with_bibtex=not no_bibtex)


@main.command()
@click.option("--member", "name", default=None, help="Only this member (substring match).")
@click.pass_context
def render(ctx: click.Context, name: str | None) -> None:
    """Read the JSON cache and write one .bib per member."""
    settings: Settings = ctx.obj["settings"]
    members = ctx.obj["members"].select(name)
    if not members:
        raise click.ClickException(f"No members matched {name!r}.")
    written = render_all(settings, members)
    click.echo(f"Wrote {len(written)} .bib file(s) to {settings.output_dir}")


@main.command(name="list")
@click.pass_context
def list_members(ctx: click.Context) -> None:
    """List configured members and whether they have a Scholar ID."""
    for m in ctx.obj["members"].members:
        # Two-char status flag so the columns line up: "OK " or "-- ".
        flag = "OK " if m.scholar_id else "-- "
        skip = "" if m.include else " [skipped]"
        click.echo(f"  {flag} {m.name}{skip}  ({m.role or '?'})")


if __name__ == "__main__":
    main()
