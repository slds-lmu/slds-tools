"""Per-pub metadata export from Google Scholar via Playwright.

Bulk export ("Select all → Export → BibTeX") on Scholar profiles is
gated behind being signed-in — anonymous viewers see no checkboxes and no
Export button. So is the per-pub Cite popup. The only thing anonymous
viewers DO get is the publication detail page itself, which renders all
the fields a real BibTeX would contain (full author names, journal,
volume, issue, pages, publisher, publication date) as visible text.

This module:
  1. Loads each member's profile in a real Chromium (via Playwright) and
     extracts the publication listing — same as `scholar.fetch_all`'s
     phase 1, but through a browser fingerprint Google trusts more.
  2. For each pub without BibTeX in the cache, navigates to its detail
     page (1 request per pub through real browser), scrapes the labeled
     fields, and assembles a BibTeX entry locally.
  3. Writes the cache after every successful pub so a CAPTCHA mid-run
     loses at most one in-flight pub.

Why the request budget is half what `scholar.fetch_all` needs: there's no
"search by title" step (we already have the citation_id from the listing,
which builds a direct detail-page URL).

Headed mode is the default. If CAPTCHA fires, the visible browser window
lets you solve it once by hand and the script continues. Headless mode is
opt-in via `headed=False` and only safe when your IP is uncautioned.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import (
    Page,
    TimeoutError as PWTimeoutError,
    sync_playwright,
)

from .config import Member, Settings
from .scholar import MemberCache, Publication, cache_path

log = logging.getLogger(__name__)


def export_all(
    settings: Settings,
    members: list[Member],
    *,
    headed: bool = True,
    pause_on_captcha: bool = True,
) -> dict[str, MemberCache | None]:
    """Drive a single browser session through every member's profile + pubs.

    One Chromium context shared across the whole run so cookies persist —
    once Scholar has trusted this session for one CAPTCHA, every later
    request benefits.

    Returns a dict like `scholar.fetch_all`: name -> MemberCache or None.
    """
    settings.cache_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, MemberCache | None] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(
            # Use a stock-looking UA to blend in. Playwright's default
            # carries "HeadlessChrome" in headless mode which is a giveaway.
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            for i, member in enumerate(members):
                if not member.scholar_id:
                    log.warning("Skipping %s: no scholar_id.", member.name)
                    results[member.name] = None
                    continue

                try:
                    cache = _export_member(
                        page, settings, member,
                        pause_on_captcha=pause_on_captcha,
                    )
                    results[member.name] = cache
                except Exception as e:  # noqa: BLE001
                    log.error("Export failed for %s: %s", member.name, e)
                    results[member.name] = None
                    continue

                if i < len(members) - 1 and settings.delay_between_members > 0:
                    time.sleep(settings.delay_between_members)
        finally:
            context.close()
            browser.close()

    return results


def _export_member(
    page: Page,
    settings: Settings,
    member: Member,
    *,
    pause_on_captcha: bool,
) -> MemberCache:
    """Get listing + per-pub metadata for one member, with incremental cache."""
    path = cache_path(settings, member)

    # Phase 1: load (or refresh) the publication listing.
    if path.exists():
        cache = MemberCache.from_file(path)
        log.info("Resuming %s from cache (%d pubs, %d already with bibtex).",
                 member.name, len(cache.publications),
                 sum(1 for p in cache.publications if p.bibtex))
    else:
        log.info("No cache yet for %s — scraping listing.", member.name)
        listing = _scrape_listing(page, member, pause_on_captcha=pause_on_captcha)
        cache = MemberCache(
            scholar_id=member.scholar_id or "",
            name=member.name,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            publications=listing,
        )
        cache.write(path)

    # Phase 2: per-pub detail-page scrape for anything still missing
    # bibtex AND inside the year filter.
    todo = [
        (i, p) for i, p in enumerate(cache.publications)
        if p.bibtex is None
        and (settings.min_year is None or (p.year is not None and p.year >= settings.min_year))
    ]
    log.info("Need detail metadata for %d/%d pubs.",
             len(todo), len(cache.publications))

    for n, (idx, pub) in enumerate(todo, start=1):
        if not pub.citation_id:
            log.debug("No citation_id for %r; skipping.", pub.title)
            continue
        try:
            bib_str = _scrape_pub_bibtex(
                page, member.scholar_id or "", pub.citation_id, pub.title,
                pause_on_captcha=pause_on_captcha,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("Detail scrape failed for %r: %s", pub.title, e)
            continue
        if bib_str:
            cache.publications[idx].bibtex = bib_str
            cache.write(path)
        if n % 10 == 0:
            log.info("  ... %d/%d pubs done", n, len(todo))
        if n < len(todo) and settings.delay_between_pubs > 0:
            time.sleep(settings.delay_between_pubs)

    log.info("Done %s (%d pubs total, %d with bibtex).",
             member.name, len(cache.publications),
             sum(1 for p in cache.publications if p.bibtex))
    return cache


def _scrape_listing(page: Page, member: Member, *, pause_on_captcha: bool) -> list[Publication]:
    """Phase 1: load profile, expand "Show more" to the end, return Publications."""
    url = f"https://scholar.google.com/citations?user={member.scholar_id}&hl=en"
    log.info("Opening %s for %s", url, member.name)
    page.goto(url, wait_until="domcontentloaded", timeout=30000)

    if _looks_like_captcha(page):
        _await_captcha(member.name, pause_on_captcha)

    _expand_full_list(page)

    # Each publication row links to its detail page. We pull title, year,
    # author/venue strings, and citation_for_view (used to build detail
    # URLs in phase 2) directly from the table.
    rows = page.evaluate("""
() => {
    const out = [];
    document.querySelectorAll('#gsc_a_b tr.gsc_a_tr').forEach(tr => {
        const titleA = tr.querySelector('a.gsc_a_at');
        const greys = tr.querySelectorAll('div.gs_gray');
        const year = (tr.querySelector('span.gsc_a_h, span.gsc_a_hc') || {}).innerText || '';
        let cit_id = '';
        if (titleA) {
            try {
                const u = new URL(titleA.href, location.origin);
                cit_id = u.searchParams.get('citation_for_view') || '';
            } catch (e) {}
        }
        out.push({
            title: (titleA && titleA.innerText) || '',
            authors: (greys[0] && greys[0].innerText) || '',
            venue: (greys[1] && greys[1].innerText) || '',
            year: year.trim(),
            citation_id: cit_id,
        });
    });
    return out;
}
    """)

    pubs: list[Publication] = []
    for r in rows:
        try:
            year = int(r["year"]) if r["year"] else None
        except ValueError:
            year = None
        pubs.append(Publication(
            title=r["title"],
            year=year,
            authors=r["authors"],
            venue=r["venue"],
            citation_id=r["citation_id"],
            bibtex=None,
        ))
    log.info("Listing scraped: %d publications.", len(pubs))
    return pubs


def _scrape_pub_bibtex(
    page: Page,
    user_id: str,
    citation_id: str,
    title: str,
    *,
    pause_on_captcha: bool,
) -> str | None:
    """Phase 2: visit a pub detail page, scrape labeled fields, build BibTeX."""
    url = (f"https://scholar.google.com/citations?view_op=view_citation"
           f"&hl=en&user={user_id}&citation_for_view={citation_id}")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)

    if _looks_like_captcha(page):
        _await_captcha(title, pause_on_captcha)

    # The detail page renders metadata as a list of label/value rows
    # inside `#gsc_oci_table`. Each row is a `gs_scl` div with two
    # children: `.gsc_oci_field` (label) and `.gsc_oci_value` (value).
    fields = page.evaluate("""
() => {
    const out = {};
    document.querySelectorAll('div.gs_scl').forEach(row => {
        const k = (row.querySelector('.gsc_oci_field') || {}).innerText;
        const v = (row.querySelector('.gsc_oci_value') || {}).innerText;
        if (k && v) out[k.trim().toLowerCase()] = v.trim();
    });
    return out;
}
    """)
    if not fields:
        log.debug("Empty fields scrape for %r", title)
        return None

    return _build_bibtex(title, fields, citation_id)


def _build_bibtex(title: str, fields: dict[str, str], citation_id: str) -> str:
    """Assemble a BibTeX entry from the labeled fields scraped off the detail page.

    Field labels Scholar uses (English UI):
      authors, publication date, journal/source/conference/book,
      volume, issue, pages, publisher, description (abstract).

    Type heuristic: @inproceedings if there's a "conference" field,
    @incollection for "book", otherwise @article. This matches what
    Scholar's own BibTeX export does.
    """
    # Determine entry type.
    if "conference" in fields:
        entry_type = "inproceedings"
        venue_key, venue = "booktitle", fields["conference"]
    elif "book" in fields:
        entry_type = "incollection"
        venue_key, venue = "booktitle", fields["book"]
    elif "source" in fields:
        entry_type = "article"
        venue_key, venue = "journal", fields["source"]
    elif "journal" in fields:
        entry_type = "article"
        venue_key, venue = "journal", fields["journal"]
    else:
        entry_type = "article"
        venue_key, venue = "journal", ""

    # Year out of "2023/3" or "2023/3/15".
    pub_date = fields.get("publication date", "")
    year_match = re.match(r"(\d{4})", pub_date)
    year = year_match.group(1) if year_match else ""

    # Citation key: surname of first author + year + first non-trivial
    # word of title. Stable as long as the listing is.
    authors_raw = fields.get("authors", "")
    first_author = authors_raw.split(",")[0].strip() if authors_raw else "anon"
    surname = first_author.split()[-1] if first_author else "anon"
    title_words = re.findall(r"[A-Za-z]+", title.lower())
    skip = {"a", "an", "the", "of", "on", "for", "in", "with", "and", "to"}
    first_word = next((w for w in title_words if w not in skip), "x")
    cite_key = _slug_key(f"{surname}{year}{first_word}")

    # Authors: turn "A B, C D, E F" into "A B and C D and E F".
    authors_bib = " and ".join(a.strip() for a in authors_raw.split(",") if a.strip())

    # Compose entry. Skip empty fields rather than emit blank ones.
    out = [f"@{entry_type}{{{cite_key},"]
    out.append(f"  title     = {{{title}}},")
    if authors_bib:
        out.append(f"  author    = {{{authors_bib}}},")
    if year:
        out.append(f"  year      = {{{year}}},")
    if venue:
        out.append(f"  {venue_key:<9} = {{{venue}}},")
    for src_key, bib_key in (("volume", "volume"), ("issue", "number"),
                              ("pages", "pages"), ("publisher", "publisher")):
        if src_key in fields:
            out.append(f"  {bib_key:<9} = {{{fields[src_key]}}},")
    # Stable note pointing back to Scholar so debugging is easier.
    out.append(f"  note      = {{Scholar citation_for_view: {citation_id}}},")
    out.append("}")
    return "\n".join(out)


def _slug_key(s: str) -> str:
    """Filename-safe BibTeX cite key (lowercase ASCII)."""
    s = re.sub(r"[^A-Za-z0-9]+", "", s)
    return s.lower() or "x"


def _expand_full_list(page: Page) -> None:
    """Click "Show more" until it stops returning new rows."""
    last_count = -1
    for _ in range(50):
        rows = page.locator("#gsc_a_b tr.gsc_a_tr").count()
        if rows == last_count:
            return
        last_count = rows
        more = page.locator("#gsc_bpf_more")
        try:
            if not more.is_visible() or more.is_disabled():
                return
        except Exception:  # noqa: BLE001
            return
        try:
            more.click(timeout=3000)
        except PWTimeoutError:
            return
        try:
            page.wait_for_function(
                f"document.querySelectorAll('#gsc_a_b tr.gsc_a_tr').length > {rows}",
                timeout=10000,
            )
        except PWTimeoutError:
            return
    log.warning("Hit 50 'Show more' iterations — capping list expansion.")


def _looks_like_captcha(page: Page) -> bool:
    """Heuristic: does this page look like a Google bot challenge?"""
    title = (page.title() or "").lower()
    if "unusual traffic" in title or "are you a robot" in title:
        return True
    body = page.evaluate("document.body && document.body.innerText.slice(0, 1000)") or ""
    body_l = body.lower()
    return ("unusual traffic" in body_l
            or "i'm not a robot" in body_l
            or "recaptcha" in body_l)


def _await_captcha(label: str, pause_on_captcha: bool) -> None:
    """Block until the user solves the visible CAPTCHA, or fail fast."""
    log.warning("CAPTCHA detected on %s.", label)
    if not pause_on_captcha:
        raise RuntimeError(f"CAPTCHA detected and pause_on_captcha=False ({label})")
    log.warning("Solve it in the browser window, then press Enter here.")
    input("  >>> press Enter when CAPTCHA is solved: ")
