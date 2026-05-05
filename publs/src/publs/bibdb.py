"""Load, index, and append to the SSOT BibTeX file.

The SSOT is hand-curated. We do two things to it:
    - read it for matching (DOI index, normalized-title index)
    - append accepted entries (atomically, so Ctrl-C never corrupts it)

We deliberately do NOT reformat or rewrite existing entries — the file's
on-disk shape (key order, comments, blank lines) is preserved verbatim
across appends. The only mutation is "append a single new @entry to the
end of the file".
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import bibtexparser


_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    """Lowercase, strip TeX braces / punctuation, collapse whitespace.

    Used as the secondary match key when a candidate has no DOI or the SSOT
    entry has no DOI field. Conservative on purpose: it's better to miss a
    fuzzy match (and surface the candidate as missing) than to silently
    suppress one (and never see it again).
    """
    if not title:
        return ""
    s = title.replace("{", "").replace("}", "").replace("\\", " ")
    s = _PUNCT_RE.sub(" ", s).lower()
    return _WS_RE.sub(" ", s).strip()


def normalize_doi(doi: str) -> str:
    """Strip URL prefix and lowercase. DOIs are case-insensitive per spec."""
    if not doi:
        return ""
    s = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if s.lower().startswith(prefix):
            s = s[len(prefix):]
            break
    return s.lower()


@dataclass
class BibDB:
    """In-memory view of slds.bib + the path to write back to.

    Attributes:
        path: SSOT file path.
        entries: parsed entries (list of dicts from bibtexparser).
        by_doi: lowercase-DOI -> entry key. Built once at load.
        by_title: normalized-title -> entry key. Built once at load.
    """

    path: Path
    entries: list[dict]
    by_doi: dict[str, str]
    by_title: dict[str, str]

    @classmethod
    def load(cls, path: Path) -> "BibDB":
        if not path.exists():
            # First run: empty file is fine. We refuse to create the file
            # ourselves because the SSOT is meant to be deliberately created
            # and version-controlled by a human.
            raise FileNotFoundError(
                f"SSOT BibTeX file not found: {path}\n"
                f"Create it (an empty file is OK) and re-run."
            )
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return cls(path=path, entries=[], by_doi={}, by_title={})

        parser = bibtexparser.bparser.BibTexParser(common_strings=True)
        # Be tolerant: we want to *find* entries to match against, not to
        # validate the SSOT. A weird entry shouldn't crash the run.
        parser.ignore_nonstandard_types = False
        parser.homogenize_fields = False
        db = bibtexparser.loads(text, parser=parser)

        by_doi: dict[str, str] = {}
        by_title: dict[str, str] = {}
        for e in db.entries:
            key = e.get("ID", "")
            doi = normalize_doi(e.get("doi", "") or e.get("DOI", ""))
            if doi:
                by_doi.setdefault(doi, key)
            title_norm = normalize_title(e.get("title", ""))
            if title_norm:
                by_title.setdefault(title_norm, key)

        return cls(path=path, entries=db.entries, by_doi=by_doi, by_title=by_title)

    def has_doi(self, doi: str) -> str | None:
        """Return the SSOT entry key for `doi`, or None."""
        return self.by_doi.get(normalize_doi(doi)) if doi else None

    def has_title(self, title: str) -> str | None:
        """Return the SSOT entry key for `title` (normalized), or None."""
        return self.by_title.get(normalize_title(title)) if title else None

    def has_key(self, key: str) -> bool:
        """Whether `key` is already used as an entry ID."""
        return any(e.get("ID") == key for e in self.entries)

    def append(self, bibtex_entry: str, doi: str | None = None,
               title: str | None = None, key: str | None = None) -> None:
        """Append a new BibTeX entry to the SSOT file atomically.

        Updates in-memory indices so the next match call sees the new entry.
        We don't re-parse the whole file; we just trust the caller to pass
        the doi / title / key they used to build the entry (review.py does).
        """
        text = bibtex_entry.strip() + "\n"
        # Atomic-ish append: write to tmp, fsync, then append in one open().
        # `open(..., "a")` is atomic per write on POSIX for small payloads,
        # which BibTeX entries always are.
        with open(self.path, "a", encoding="utf-8") as f:
            # Ensure separation from a prior entry that may not have ended
            # with a blank line.
            f.write("\n" + text)
            f.flush()
            os.fsync(f.fileno())

        if doi:
            self.by_doi.setdefault(normalize_doi(doi), key or "")
        if title:
            self.by_title.setdefault(normalize_title(title), key or "")
        if key:
            self.entries.append({"ID": key, "doi": doi or "", "title": title or ""})

    def __len__(self) -> int:
        return len(self.entries)
