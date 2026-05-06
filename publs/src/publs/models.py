"""Shared record types for external sources and matching."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Candidate:
    """One publication record returned by an external source.

    All sources normalize their result to this shape so `match.py` and
    `review.py` don't care which API the candidate came from.

    Attributes:
        source:        e.g. "openalex" / "crossref" / "scholar"
        source_id:     stable ID at the source (OpenAlex work ID, etc.)
        title:         publication title (no TeX braces)
        year:          publication year, if known
        authors:       list of "First Last" strings (display order, not BibTeX)
        venue:         journal / conference name, if known
        doi:           DOI (no URL prefix), if known
        type:          OpenAlex/Crossref-style type string ("journal-article", ...)
        url:           landing page URL, if known
        is_preprint:   True if the source-side signals say this is a
                       preprint / repository deposit rather than a final
                       publication. Set by the source during normalization
                       so downstream code stays source-agnostic.
        raw:           original record from the source (for debugging / fallback)
    """

    source: str
    source_id: str
    title: str
    year: int | None
    authors: list[str] = field(default_factory=list)
    venue: str = ""
    doi: str = ""
    type: str = ""
    url: str = ""
    is_preprint: bool = False
    raw: dict = field(default_factory=dict)
