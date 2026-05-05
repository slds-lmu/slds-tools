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
    min_year: int | None      # see config.yaml
    mailto: str

    @classmethod
    def load(cls, path: Path) -> "Settings":
        raw = yaml.safe_load(path.read_text())
        base = path.parent
        return cls(
            ssot_path=(base / raw["ssot_path"]).resolve(),
            min_year=raw.get("min_year"),
            mailto=str(raw.get("mailto", "")),
        )


@dataclass(frozen=True)
class Member:
    """One person from members.yaml.

    Each per-platform ID is optional. A member with `openalex_id: null`
    is silently skipped for OpenAlex queries (and likewise for `orcid`
    -> Crossref and `scholar_id` -> Google Scholar). Missing IDs are
    surfaced as a LOUD end-of-run warning so they're never invisible,
    but they don't fail the run.
    """

    name: str
    openalex_id: str | None = None    # https://openalex.org/A...
    orcid: str | None = None          # used by Crossref + ORCID itself
    scholar_id: str | None = None     # https://scholar.google.com/?user=...
    include: bool = True


# Per-source mapping. Drives the end-of-run gap warning and the
# per-member skip in each command. Keep in lockstep with Source enums
# in publs.sources when those land.
ID_FIELD_BY_SOURCE: dict[str, str] = {
    "openalex": "openalex_id",
    "crossref": "orcid",
    "scholar":  "scholar_id",
}


@dataclass(frozen=True)
class MemberList:
    members: list[Member] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "MemberList":
        raw = yaml.safe_load(path.read_text())
        members = [
            Member(
                name=m["name"],
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
