"""OpenAlex source: fetch a member's works as Candidate records.

Resolution order for the OpenAlex author ID:
    1. members.yaml `openalex_id`        (most reliable; no API hit needed)
    2. members.yaml `orcid`              (one /authors/orcid:... call)
    3. name search                       (fragile; logs the top 3 hits)

Once the author ID is known, paging through /works with
`filter=author.id:<id>` gives us every work OpenAlex has linked to them.
We don't fetch publisher BibTeX here — that happens in review.py only for
candidates the user wants to accept, so `publs check` can do a fast
read-only scan of all members without hammering doi.org.
"""
from __future__ import annotations

import logging
import time

import httpx

from ..config import Member, Settings
from ..models import Candidate

log = logging.getLogger(__name__)

OPENALEX = "https://api.openalex.org"
PER_PAGE = 200          # OpenAlex max page size
INTER_PAGE_SLEEP = 0.1  # politeness; OpenAlex doesn't enforce, we do


def _client(settings: Settings) -> httpx.Client:
    headers = {"User-Agent": f"publs ({settings.mailto or 'no-mailto'})"}
    return httpx.Client(headers=headers, timeout=30)


def _params(settings: Settings, **extra) -> dict:
    p = {"mailto": settings.mailto} if settings.mailto else {}
    p.update(extra)
    return p


def resolve_author_id(client: httpx.Client, member: Member,
                      settings: Settings) -> str | None:
    """Return an OpenAlex author URL ('https://openalex.org/A...'), or None.

    Tries openalex_id, orcid, name search in that order.
    """
    if member.openalex_id:
        # OpenAlex stores IDs as URLs; the API also accepts the bare suffix.
        if member.openalex_id.startswith("http"):
            return member.openalex_id
        return f"https://openalex.org/{member.openalex_id}"

    if member.orcid:
        try:
            r = client.get(
                f"{OPENALEX}/authors/orcid:{member.orcid}",
                params=_params(settings),
            )
            if r.status_code == 200:
                return r.json().get("id")
            log.warning("ORCID lookup failed for %s (%s): %d",
                        member.name, member.orcid, r.status_code)
        except httpx.HTTPError as e:
            log.warning("ORCID lookup error for %s: %s", member.name, e)

    # Name search fallback. Surface the top 3 so a misranked match is
    # visible in the logs.
    log.warning("Falling back to name search for %s — verify the result.",
                member.name)
    r = client.get(
        f"{OPENALEX}/authors",
        params=_params(settings, search=member.name, **{"per-page": 5}),
    )
    r.raise_for_status()
    hits = r.json().get("results", [])
    if not hits:
        log.error("No OpenAlex author found for %s", member.name)
        return None
    log.info("Top OpenAlex candidates for %r:", member.name)
    for h in hits[:3]:
        log.info("  - %s (id=%s, works=%d, cited_by=%d)",
                 h.get("display_name"), h.get("id"),
                 h.get("works_count", 0), h.get("cited_by_count", 0))
    return hits[0].get("id")


def _to_candidate(work: dict) -> Candidate:
    title = (work.get("title") or "").replace("{", "").replace("}", "").strip()
    authors = []
    for a in work.get("authorships") or []:
        name = ((a.get("author") or {}).get("display_name") or "").strip()
        if name:
            authors.append(name)
    location = work.get("primary_location") or {}
    source = location.get("source") or {}
    venue = (source.get("display_name") or "").strip()
    doi = (work.get("doi") or "").replace("https://doi.org/", "").lower()
    return Candidate(
        source="openalex",
        source_id=work.get("id", ""),
        title=title,
        year=work.get("publication_year"),
        authors=authors,
        venue=venue,
        doi=doi,
        type=work.get("type") or "",
        url=location.get("landing_page_url") or "",
        raw=work,
    )


def fetch(member: Member, settings: Settings) -> list[Candidate]:
    """Return all OpenAlex works for `member` as Candidate records.

    Returns an empty list if the author can't be resolved. Applies
    `settings.min_year` here so downstream code never sees old works.
    """
    with _client(settings) as client:
        author_id = resolve_author_id(client, member, settings)
        if not author_id:
            return []
        log.info("OpenAlex author for %s: %s", member.name, author_id)

        candidates: list[Candidate] = []
        cursor = "*"
        while cursor:
            r = client.get(
                f"{OPENALEX}/works",
                params=_params(
                    settings,
                    filter=f"author.id:{author_id}",
                    cursor=cursor,
                    **{"per-page": PER_PAGE},
                ),
            )
            r.raise_for_status()
            data = r.json()
            for w in data.get("results") or []:
                cand = _to_candidate(w)
                if settings.min_year is not None and (cand.year or 0) < settings.min_year:
                    continue
                candidates.append(cand)
            cursor = (data.get("meta") or {}).get("next_cursor")
            time.sleep(INTER_PAGE_SLEEP)
    return candidates


def fetch_bibtex_for_doi(doi: str, settings: Settings) -> str | None:
    """Ask doi.org for publisher-blessed BibTeX via content negotiation.

    Returns None on failure (network error, non-200, or non-BibTeX
    response). Used by review.py only for accepted candidates, so a
    flaky publisher endpoint doesn't block the whole `check` flow.
    """
    if not doi:
        return None
    headers = {
        "Accept": "application/x-bibtex; charset=utf-8",
        "User-Agent": f"publs ({settings.mailto or 'no-mailto'})",
    }
    try:
        r = httpx.get(
            f"https://doi.org/{doi}",
            headers=headers,
            follow_redirects=True,
            timeout=20,
        )
    except httpx.HTTPError as e:
        log.warning("DOI fetch error for %s: %s", doi, e)
        return None
    if r.status_code != 200:
        log.warning("DOI %s returned %d", doi, r.status_code)
        return None
    text = r.text.strip()
    if not text.startswith("@"):
        log.warning("DOI %s did not return BibTeX (got %r...)", doi, text[:60])
        return None
    return text


def build_bibtex_from_candidate(cand: Candidate) -> str:
    """Synthesize a BibTeX entry from a Candidate when no DOI is available.

    Lower fidelity than publisher BibTeX (initials may be wrong, no page
    numbers, etc.) but lets us still produce a usable entry for preprints,
    theses, and unindexed venues.
    """
    title = cand.title
    # OpenAlex "First Last" -> BibTeX "Last, First"
    bib_authors = []
    for name in cand.authors:
        parts = name.rsplit(" ", 1)
        bib_authors.append(f"{parts[1]}, {parts[0]}" if len(parts) == 2 else name)
    authors_str = " and ".join(bib_authors)

    entry_type = {
        "article": "article",
        "journal-article": "article",
        "book-chapter": "incollection",
        "book": "book",
        "proceedings-article": "inproceedings",
        "conference-paper": "inproceedings",
        "preprint": "misc",
        "dissertation": "phdthesis",
    }.get(cand.type, "misc")

    surname = bib_authors[0].split(",")[0].lower() if bib_authors else "anon"
    title_word = next((w.lower() for w in title.split() if len(w) > 4), "untitled")
    key = "".join(c for c in f"{surname}{cand.year or ''}{title_word}" if c.isalnum())

    fields = [f"  title = {{{title}}}"]
    if authors_str:
        fields.append(f"  author = {{{authors_str}}}")
    if cand.year:
        fields.append(f"  year = {{{cand.year}}}")
    if cand.venue:
        fields.append(f"  journal = {{{cand.venue}}}")
    if cand.doi:
        fields.append(f"  doi = {{{cand.doi}}}")
    if cand.url:
        fields.append(f"  url = {{{cand.url}}}")

    return "@" + entry_type + "{" + key + ",\n" + ",\n".join(fields) + "\n}"
