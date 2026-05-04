"""Config loading for publs.

Parses two YAML files into immutable dataclasses used throughout the project:

    config.yaml   -> Settings (paths, filters, scrape behavior)
    members.yaml  -> MemberList of Member rows

Everything downstream takes Settings + Member(s) as input — there is no other
source of configuration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Settings:
    """Global knobs loaded from config.yaml.

    `cache_dir` and `output_dir` are stored as absolute paths (resolved
    against the directory of the config file at load time), so callers don't
    need to know where the config came from.
    """

    cache_dir: Path
    output_dir: Path
    min_year: int | None
    cache_ttl_days: int
    proxy: str
    delay_between_members: float
    filename_style: str

    @classmethod
    def load(cls, path: Path) -> "Settings":
        """Parse config.yaml at `path` into a Settings instance.

        Relative paths in the YAML (cache_dir, output_dir) are resolved
        relative to the YAML file itself, not the process CWD — so the tool
        works the same no matter where it's invoked from.
        """
        raw = yaml.safe_load(path.read_text())
        base = path.parent
        return cls(
            cache_dir=(base / raw["cache_dir"]).resolve(),
            output_dir=(base / raw["output_dir"]).resolve(),
            min_year=raw.get("min_year"),
            cache_ttl_days=int(raw.get("cache_ttl_days", 7)),
            proxy=str(raw.get("proxy", "free")),
            delay_between_members=float(raw.get("delay_between_members", 5)),
            filename_style=str(raw.get("filename_style", "lastname_firstname")),
        )


@dataclass(frozen=True)
class Member:
    """One person from members.yaml.

    `scholar_id` may be None — those members are skipped (with a warning) by
    `fetch_all`. `include=False` lets you keep a row in the YAML but exclude
    it from runs (e.g. for alumni or admins).
    """

    name: str
    scholar_id: str | None
    role: str | None = None
    include: bool = True

    def slug(self, style: str) -> str:
        """Return a filename-safe slug for this member.

        Used for both the cache JSON path and the rendered .bib filename so
        they stay in lockstep. `style="lastname_firstname"` produces
        e.g. "bischl-bernd"; any other value falls back to a plain
        space-joined slug.
        """
        parts = self.name.split()
        if not parts:
            return "unknown"
        if style == "lastname_firstname":
            # Treat the last whitespace-separated token as the surname; works
            # for German double-barrelled given names ("Hans Peter Müller"),
            # but is wrong for compound surnames ("van der Berg"). Add a
            # `slug:` override field on Member if that becomes a real issue.
            last = parts[-1]
            first = "-".join(parts[:-1]) if len(parts) > 1 else ""
            base = f"{last}-{first}" if first else last
        else:
            base = "-".join(parts)
        return _slugify(base)


def _slugify(s: str) -> str:
    """Lowercase, fold German umlauts to ASCII, drop everything non-alnum."""
    # Keep the umlaut map explicit; `unicodedata.normalize` would turn "ü"
    # into "u" not "ue", which is wrong for German names.
    table = str.maketrans({
        "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
        "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
    })
    s = s.translate(table)
    out = []
    for ch in s.lower():
        if ch.isalnum() or ch == "-":
            out.append(ch)
        elif ch in (" ", "_"):
            out.append("-")
    return "".join(out).strip("-")


@dataclass(frozen=True)
class MemberList:
    """Wrapper around the parsed members.yaml.

    A thin container, but having it as a dataclass keeps `select()` close to
    the data and lets callers pass `MemberList` instead of bare lists.
    """

    members: list[Member] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "MemberList":
        """Parse members.yaml at `path` into a MemberList."""
        raw = yaml.safe_load(path.read_text())
        members = [
            Member(
                name=m["name"],
                scholar_id=m.get("scholar_id"),
                role=m.get("role"),
                include=m.get("include", True),
            )
            for m in raw.get("members", [])
        ]
        return cls(members=members)

    def select(self, name: str | None) -> list[Member]:
        """Filter members for CLI use.

        - `name=None` -> all members where include=True
        - `name="bischl"` -> any member whose name contains "bischl"
          (case-insensitive). An exact match is also accepted; substring
          matching makes `--member bischl` and `--member "Bernd Bischl"`
          both work.
        """
        if name is None:
            return [m for m in self.members if m.include]
        wanted = name.lower()
        return [
            m for m in self.members
            if m.include and (m.name.lower() == wanted or wanted in m.name.lower())
        ]
