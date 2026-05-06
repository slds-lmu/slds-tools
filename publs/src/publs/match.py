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

from .bibdb import BibDB, normalize_title
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


# --- Within-batch preprint/published dedup --------------------------------
#
# OpenAlex returns the bioRxiv preprint and the journal version of the
# same paper as two unrelated works (different DOIs, no `versions` link).
# Without dedup, both surface as "missing" and the user gets prompted to
# add both. Dedup happens *within* a single fetched batch only — a
# preprint already in the SSOT vs. a published candidate today is a
# different problem (cross-batch / cross-time) and not handled here.

_JACCARD_THRESHOLD = 0.8
_YEAR_DELTA_MAX = 2


def _surname(author: str) -> str:
    """First-author surname for grouping (last whitespace-token, lowercased)."""
    parts = (author or "").split()
    return parts[-1].lower() if parts else ""


def _title_tokens(title: str) -> set[str]:
    return set(normalize_title(title).split())


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return (len(a & b) / len(union)) if union else 0.0


def dedup_preprint_pairs(
    candidates: list[Candidate],
) -> tuple[list[Candidate], list[Candidate]]:
    """Suppress preprint candidates whose published twin is in the same batch.

    Groups candidates by (same first-author surname, |year delta| <= 2,
    title token Jaccard >= 0.8). Within each group with at least one
    non-preprint, drops the preprint(s). Single-member groups and groups
    consisting only of preprints pass through unchanged.

    Returns (kept, suppressed). Order of `kept` follows the input order
    of the surviving candidates.
    """
    n = len(candidates)
    if n < 2:
        return list(candidates), []

    titles = [_title_tokens(c.title) for c in candidates]
    surnames = [_surname(c.authors[0]) if c.authors else "" for c in candidates]

    # Union-find: collapse any pair that satisfies the grouping rule.
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        if not surnames[i]:
            continue
        for j in range(i + 1, n):
            if surnames[i] != surnames[j]:
                continue
            yi, yj = candidates[i].year or 0, candidates[j].year or 0
            if abs(yi - yj) > _YEAR_DELTA_MAX:
                continue
            if _jaccard(titles[i], titles[j]) >= _JACCARD_THRESHOLD:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    keep_idx: set[int] = set()
    suppressed: list[Candidate] = []
    for members in groups.values():
        if len(members) == 1:
            keep_idx.add(members[0])
            continue
        any_published = any(not candidates[i].is_preprint for i in members)
        if not any_published:
            keep_idx.update(members)
            continue
        for i in members:
            if candidates[i].is_preprint:
                suppressed.append(candidates[i])
            else:
                keep_idx.add(i)

    kept = [c for i, c in enumerate(candidates) if i in keep_idx]
    return kept, suppressed


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
