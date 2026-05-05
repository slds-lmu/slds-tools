"""Decide whether a Candidate is already in the SSOT BibDB.

Match precedence:
    1. DOI (after normalization). Definitive when present on both sides.
    2. Normalized title. Required for entries without DOI (preprints,
       reports, talks). Conservative — see normalize_title in bibdb.py.

Output:
    "present"  — already in the SSOT, skip.
    "missing"  — surface to user as a new suggestion.
"""
from __future__ import annotations

from dataclasses import dataclass

from .bibdb import BibDB
from .models import Candidate


@dataclass(frozen=True)
class MatchResult:
    status: str         # "present" | "missing"
    matched_key: str | None  # SSOT entry key when status == "present"


def match(cand: Candidate, db: BibDB) -> MatchResult:
    if cand.doi:
        key = db.has_doi(cand.doi)
        if key:
            return MatchResult("present", key)
    if cand.title:
        key = db.has_title(cand.title)
        if key:
            return MatchResult("present", key)
    return MatchResult("missing", None)


def split_missing(candidates: list[Candidate], db: BibDB) -> list[Candidate]:
    """Return only the candidates that aren't already in the SSOT."""
    return [c for c in candidates if match(c, db).status == "missing"]
