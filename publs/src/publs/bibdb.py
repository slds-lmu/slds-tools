"""Load, index, and mutate the SSOT BibTeX file.

The SSOT is hand-curated. We do three things to it:
    - read it for matching (DOI index, normalized-title index)
    - append a new entry, atomically (single-write open(a) + fsync)
    - replace an existing entry with a diff-confirmed update,
      atomically (tmpfile in same dir + fsync + os.replace)

Existing entries are never silently reformatted. Append leaves the
file's prior bytes untouched, and replace swaps exactly one entry
block while preserving the rest of the file verbatim.
"""
from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import bibtexparser


_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")

# Matches "@type{key," at the start of a BibTeX entry. We use this both
# to find entry spans on disk and to rekey a freshly-built entry block
# before splicing it in (replace path).
_ENTRY_HEADER_RE = re.compile(
    r"@(?P<type>\w+)\s*\{\s*(?P<key>[^,\s}]+)\s*,",
)
# Pseudo-entry types that are not publication entries; skipped by the
# span scanner so they never collide with citation keys.
_NON_ENTRY_TYPES = frozenset({"comment", "string", "preamble"})


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


def _scan_entry_spans(text: str) -> dict[str, tuple[int, int]]:
    """Locate each @entry block's (start, end) byte offsets in `text`.

    Walks the text once, finding `@type{key,` headers and tracking brace
    balance to the closing `}`. Skips @comment / @string / @preamble.
    On duplicate keys, the first occurrence wins (matches bibtexparser).
    Malformed (unbalanced) blocks are silently skipped rather than raising,
    so a half-edited file doesn't block the whole tool.
    """
    spans: dict[str, tuple[int, int]] = {}
    for m in _ENTRY_HEADER_RE.finditer(text):
        if m.group("type").lower() in _NON_ENTRY_TYPES:
            continue
        key = m.group("key")
        brace_open = text.find("{", m.start())
        if brace_open == -1:
            continue
        depth = 1
        i = brace_open + 1
        while i < len(text) and depth > 0:
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            i += 1
        if depth != 0:
            continue
        spans.setdefault(key, (m.start(), i))
    return spans


@dataclass
class BibDB:
    """In-memory view of slds.bib + the path to write back to.

    Attributes:
        path:        SSOT file path.
        entries:     parsed entries (list of dicts from bibtexparser).
        by_doi:      lowercase-DOI -> entry key. Built on load.
        by_title:    normalized-title -> entry key. Built on load.
        raw_text:    file contents as last read from disk. Used by replace()
                     to splice a new block in without disturbing surrounding
                     bytes (formatting, comments, blank lines).
        entry_spans: entry key -> (start, end) byte offsets in raw_text.
                     Built on load and refreshed after every mutation.
    """

    path: Path
    entries: list[dict]
    by_doi: dict[str, str]
    by_title: dict[str, str]
    raw_text: str = ""
    entry_spans: dict[str, tuple[int, int]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "BibDB":
        """Read the SSOT file and build all in-memory indices.

        First-run friendly: an empty (or whitespace-only) file is OK and
        yields an empty DB. A missing file is an error — the SSOT is
        meant to be deliberately created and version-controlled by a
        human, so the tool will not fabricate one.
        """
        if not path.exists():
            raise FileNotFoundError(
                f"SSOT BibTeX file not found: {path}\n"
                f"Create it (an empty file is OK) and re-run."
            )
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return cls(path=path, entries=[], by_doi={}, by_title={},
                       raw_text=text, entry_spans={})

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

        return cls(
            path=path, entries=db.entries, by_doi=by_doi, by_title=by_title,
            raw_text=text, entry_spans=_scan_entry_spans(text),
        )

    def has_doi(self, doi: str) -> str | None:
        """Return the SSOT entry key for `doi`, or None."""
        return self.by_doi.get(normalize_doi(doi)) if doi else None

    def has_title(self, title: str) -> str | None:
        """Return the SSOT entry key for `title` (normalized), or None."""
        return self.by_title.get(normalize_title(title)) if title else None

    def has_key(self, key: str) -> bool:
        """Whether `key` is already used as an entry ID."""
        return key in self.entry_spans

    def get_entry_text(self, key: str) -> str:
        """Return the verbatim text of the SSOT block for `key`.

        Used by the replace path to render a unified diff of old vs
        proposed. Raises KeyError if the entry isn't in the SSOT.
        """
        if key not in self.entry_spans:
            raise KeyError(key)
        s, e = self.entry_spans[key]
        return self.raw_text[s:e]

    def append(self, bibtex_entry: str) -> str:
        """Append a new BibTeX entry to the SSOT file atomically.

        Inputs:
            bibtex_entry: a complete '@type{key, ... }' block.

        Returns:
            the citation key extracted from the entry.

        Side-effects:
            One open(path, 'a') + write + fsync, then a full reload
            from disk so all in-memory indices (DOI, title, key, spans)
            reflect the new file contents.
        """
        text = bibtex_entry.strip() + "\n"
        with open(self.path, "a", encoding="utf-8") as f:
            # Leading newline guarantees separation even if a prior entry
            # didn't end with one.
            f.write("\n" + text)
            f.flush()
            os.fsync(f.fileno())
        self._reload()
        m = _ENTRY_HEADER_RE.search(bibtex_entry)
        return m.group("key") if m else ""

    def replace(self, old_key: str, new_bibtex_entry: str) -> None:
        """Replace SSOT entry `old_key` with `new_bibtex_entry`, atomically.

        Inputs:
            old_key:           citation key of the entry already in the SSOT.
            new_bibtex_entry:  a complete '@type{anything, ... }' block.
                               Its citation key is rewritten to `old_key`
                               before writing, so external documents that
                               cite this entry don't break.

        Side-effects:
            tmpfile + fsync + os.replace, then a full reload from disk.
            The SSOT is never half-written even on Ctrl-C / power loss:
            os.replace is atomic on POSIX, and on failure the tmpfile
            is unlinked.
        """
        if old_key not in self.entry_spans:
            raise KeyError(old_key)
        new_block = self._rekey(new_bibtex_entry, old_key).strip()
        start, end = self.entry_spans[old_key]
        # Splice without touching surrounding bytes: prior entries,
        # blank lines, and comments stay verbatim.
        new_text = self.raw_text[:start] + new_block + self.raw_text[end:]

        fd, tmp = tempfile.mkstemp(
            prefix=".publs.", suffix=".bib.tmp", dir=str(self.path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(new_text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            # Best-effort cleanup; we're already raising whatever caused
            # the failure, don't shadow it.
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            raise

        self._reload()

    def _reload(self) -> None:
        """Re-read the SSOT from disk and refresh every in-memory index."""
        fresh = BibDB.load(self.path)
        self.entries = fresh.entries
        self.by_doi = fresh.by_doi
        self.by_title = fresh.by_title
        self.raw_text = fresh.raw_text
        self.entry_spans = fresh.entry_spans

    @staticmethod
    def _rekey(bibtex_entry: str, new_key: str) -> str:
        """Rewrite the first '@type{KEY,' header to use `new_key`.

        Raises ValueError if no header is found, so a malformed entry
        never silently survives into the SSOT.
        """
        new, n = _ENTRY_HEADER_RE.subn(
            lambda m: f"@{m.group('type')}{{{new_key},",
            bibtex_entry, count=1,
        )
        if n == 0:
            raise ValueError("no @type{key,...} header in entry text")
        return new

    def __len__(self) -> int:
        return len(self.entries)
