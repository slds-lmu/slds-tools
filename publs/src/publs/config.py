"""Config + member loading.

Two YAML files drive everything:

    config.yaml   -> Settings  (paths, filters, source selection)
    members.yaml  -> MemberList of Member rows (one per SLDS person)

Downstream code takes Settings + Member(s) and never reads YAML directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Settings:
    """Global knobs from config.yaml.

    `ssot_path` is resolved to an absolute path against the directory of the
    YAML file at load time, so callers don't need to know where the config
    came from.
    """

    ssot_path: Path
    min_year: int | None
    mailto: str
    enabled_sources: tuple[str, ...]

    @classmethod
    def load(cls, path: Path) -> "Settings":
        raw = yaml.safe_load(path.read_text())
        base = path.parent
        sources = tuple(raw.get("enabled_sources") or ["openalex"])
        return cls(
            ssot_path=(base / raw["ssot_path"]).resolve(),
            min_year=raw.get("min_year"),
            mailto=str(raw.get("mailto", "")),
            enabled_sources=sources,
        )


@dataclass(frozen=True)
class Member:
    """One person from members.yaml.

    Identifier fields are tried in priority order by each source:
    `openalex_id` (most reliable), then `orcid`, then a name search.
    `scholar_id` is reserved for the future Google Scholar integration.
    """

    name: str
    role: str | None = None
    openalex_id: str | None = None
    orcid: str | None = None
    scholar_id: str | None = None
    include: bool = True

    @property
    def surname(self) -> str:
        """Last whitespace-separated token of the display name."""
        parts = self.name.split()
        return parts[-1] if parts else self.name


@dataclass(frozen=True)
class MemberList:
    members: list[Member] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "MemberList":
        raw = yaml.safe_load(path.read_text())
        members = [
            Member(
                name=m["name"],
                role=m.get("role"),
                openalex_id=m.get("openalex_id"),
                orcid=m.get("orcid"),
                scholar_id=m.get("scholar_id"),
                include=m.get("include", True),
            )
            for m in raw.get("members", [])
        ]
        return cls(members=members)

    def select(self, name: str | None) -> list[Member]:
        """Filter members for CLI use.

        - `name=None`     -> all members where include=True
        - `name="bischl"` -> any included member whose display name contains
          "bischl" (case-insensitive). Exact match also accepted.
        """
        if name is None:
            return [m for m in self.members if m.include]
        wanted = name.lower()
        return [
            m for m in self.members
            if m.include and (m.name.lower() == wanted or wanted in m.name.lower())
        ]
