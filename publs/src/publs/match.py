"""Decide whether a Candidate is already in the SSOT BibDB.

Match precedence:
    1. DOI (after normalization). Definitive when present on both sides.
    2. Normalized title. Required for entries without DOI (preprints,
       reports, talks). Conservative — see normalize_title in bibdb.py.

Output statuses:
    "present"  — already in the SSOT, skip.
    "missing"  — surface to user as a new suggestion (append path).
    "outdated" — already in the SSOT but the candidate strictly adds
                 fields that are missing/empty in the SSOT entry.
                 Surface to user as a unified-diff fix (replace path,
                 implemented additively in review.py).

"outdated" is conservative on purpose: it only fires when the candidate
*adds* non-empty metadata, never when fields *differ*. Pure mismatches
(different DOI, different year) need human attention but auto-flagging
them as a fix would presume the candidate is right and produce noise.

We deliberately do NOT branch on "looks hand-curated vs tool-written"
heuristics. Every entry is treated the same; the user's veto at the
diff-confirm prompt is the only place provenance gets a vote.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .bibdb import BibDB
from .models import Candidate


@dataclass(frozen=True)
class FieldFix:
    """One additive fix proposed for an existing SSOT entry.

    Attributes:
        label:    human-facing name shown in the prompt ("doi", "year",
                  "venue") — independent of the BibTeX field name.
        bib_name: BibTeX field name to write ("doi", "year", "journal"
                  or "booktitle"). Differs from `label` for venue,
                  whose physical field depends on the entry type.
        value:    string to insert.
    """

    label: str
    bib_name: str
    value: str


@dataclass(frozen=True)
class MatchResult:
    """Outcome of matching one Candidate against the SSOT.

    `fixes` carries the additive patches when status is "outdated";
    empty otherwise. `matched_key` is set on "present" and "outdated".
    """

    status: str
    matched_key: str | None
    fixes: tuple[FieldFix, ...] = field(default_factory=tuple)


def _entry_field(entry: dict, name: str) -> str:
    """Case-insensitive field lookup on a parsed bibtexparser entry.

    bibtexparser is configured with homogenize_fields=False so original
    field-name casing is preserved. We try lowercase first (most common),
    then uppercase, then a last-resort case-insensitive scan.
    """
    if name in entry:
        return entry[name] or ""
    upper = name.upper()
    if upper in entry:
        return entry[upper] or ""
    for k, v in entry.items():
        if k.lower() == name:
            return v or ""
    return ""


def _venue_field_name(entry: dict) -> str:
    """Return 'booktitle' for proceedings entries, 'journal' otherwise."""
    etype = (entry.get("ENTRYTYPE") or "").lower()
    if etype in ("inproceedings", "conference", "proceedings"):
        return "booktitle"
    return "journal"


def _detect_fixes(cand: Candidate, entry: dict) -> tuple[FieldFix, ...]:
    """Field additions the candidate strictly contributes to `entry`.

    A field counts as "added" only when the SSOT value is missing/empty
    and the candidate value is non-empty. Mismatches are NOT reported.
    `venue` is matched against either `journal` or `booktitle` on the
    SSOT side, since BibTeX stores conference vs. journal venues
    separately; the chosen target field on write follows the entry type.
    """
    fixes: list[FieldFix] = []
    if cand.doi and not _entry_field(entry, "doi"):
        fixes.append(FieldFix("doi", "doi", cand.doi))
    if cand.year and not str(_entry_field(entry, "year")).strip():
        fixes.append(FieldFix("year", "year", str(cand.year)))
    if cand.venue:
        ssot_venue = _entry_field(entry, "journal") or _entry_field(entry, "booktitle")
        if not ssot_venue:
            fixes.append(FieldFix("venue", _venue_field_name(entry), cand.venue))
    return tuple(fixes)


def match(cand: Candidate, db: BibDB) -> MatchResult:
    """Bucket a candidate as present / missing / outdated. Pure read."""
    matched_key: str | None = None
    if cand.doi:
        matched_key = db.has_doi(cand.doi)
    if not matched_key and cand.title:
        matched_key = db.has_title(cand.title)
    if not matched_key:
        return MatchResult("missing", None)

    entry = next((e for e in db.entries if e.get("ID") == matched_key), None)
    fixes = _detect_fixes(cand, entry) if entry else ()
    if fixes:
        return MatchResult("outdated", matched_key, fixes)
    return MatchResult("present", matched_key)


def split_review_set(
    candidates: list[Candidate], db: BibDB,
) -> tuple[list[Candidate], list[tuple[Candidate, str, tuple[FieldFix, ...]]]]:
    """Bucket candidates into (missing, outdated) for the review loop."""
    missing: list[Candidate] = []
    outdated: list[tuple[Candidate, str, tuple[FieldFix, ...]]] = []
    for c in candidates:
        r = match(c, db)
        if r.status == "missing":
            missing.append(c)
        elif r.status == "outdated":
            outdated.append((c, r.matched_key or "", r.fixes))
    return missing, outdated


def split_missing(candidates: list[Candidate], db: BibDB) -> list[Candidate]:
    """Return only the candidates that aren't already in the SSOT."""
    return [c for c in candidates if match(c, db).status == "missing"]
