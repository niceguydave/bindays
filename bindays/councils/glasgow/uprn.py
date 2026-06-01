"""Resolve a postcode/address into a UPRN via the council's address search.

This module is **Glasgow-specific** (the GCC ASP.NET address-search flow). It is
one half of the Glasgow provider in ``bindays.councils.glasgow``; other councils
may not even use UPRNs. See ``bindays.council`` for the interface and the current
single-council limitation.


The address search page (``AddressSearch.aspx``) is an ASP.NET WebForms page, so
the lookup is a multi-step dance, not a simple GET:

1. **Load** the page to get the session cookie and the hidden ``__VIEWSTATE`` /
   ``__EVENTVALIDATION`` tokens that every postback must echo back.
2. **Search**: POST those tokens plus the search term. The response is a paged
   grid of matching addresses. Each address row has a "Select" link
   (``__doPostBack('...$Select0', '')``); the grid also has a numbered pager
   (``...$Page2``, ``...$Page3``). The UPRN is *not* in this grid.
3. **Page** (if needed): a bare postcode is split across pages of ~16 addresses,
   so we follow the pager to collect every address.
4. **Select**: POST the chosen row's postback target *while on the page it lives
   on*. The server redirects to ``CollectionsCalendar.aspx?UPRN=<uprn>`` - that
   URL is where we read the UPRN.

Performance note: the council server is slow. ``search_addresses`` walks all
pages once; ``resolve_uprn`` only resolves the single address you pick.
"""

import re
from collections.abc import Iterator

import requests
from bs4 import BeautifulSoup, Tag

from ...models import AddressOption

SEARCH_URL = (
    "https://onlineservices.glasgow.gov.uk/forms/"
    "refuseandrecyclingcalendar/AddressSearch.aspx"
)
HEADERS = {"User-Agent": "Mozilla/5.0 (bindays)"}

_SEARCH_FIELD = "ctl00$Application$Addresses$Search"
_BUTTON = "ctl00$Application$Addresses$ImageButton"
_UPRN_RE = re.compile(r"UPRN=(\d{6,})", re.IGNORECASE)
_POSTBACK_RE = re.compile(r"__doPostBack\('([^']+)'")
_PAGE_TARGET_RE = re.compile(r"\$Page(\d+)$")

# Safety cap so a malformed pager can never loop forever.
_MAX_PAGES = 60


def _hidden_fields(soup: BeautifulSoup) -> dict[str, str]:
    fields: dict[str, str] = {}
    for name in (
        "__VIEWSTATE",
        "__VIEWSTATEGENERATOR",
        "__EVENTVALIDATION",
        "__EVENTTARGET",
        "__EVENTARGUMENT",
    ):
        tag = soup.find("input", attrs={"name": name})
        value = tag.get("value", "") if isinstance(tag, Tag) else ""
        fields[name] = value if isinstance(value, str) else ""
    return fields


def _collect_rows(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """Address rows on the current page as (label, select_postback_target)."""
    rows: list[tuple[str, str]] = []
    for anchor in soup.find_all("a", href=_POSTBACK_RE):
        match = _POSTBACK_RE.search(anchor["href"])
        if match is None:
            continue
        target = match.group(1)
        if _PAGE_TARGET_RE.search(target):
            continue  # this is a pager link, not an address
        row = anchor.find_parent("tr")
        if row is None:
            continue
        cells = row.find_all("td")
        label = cells[-1].get_text(strip=True) if cells else ""
        if label and not label.isdigit():
            rows.append((label, target))
    return rows


def _pager_targets(soup: BeautifulSoup) -> dict[int, str]:
    """Map of {page_number: postback_target} for pager links on this page."""
    targets: dict[int, str] = {}
    for anchor in soup.find_all("a", href=_POSTBACK_RE):
        match = _POSTBACK_RE.search(anchor["href"])
        if match is None:
            continue
        m = _PAGE_TARGET_RE.search(match.group(1))
        if m:
            targets[int(m.group(1))] = match.group(1)
    return targets


def _iter_pages(
    session: requests.Session, query: str, *, timeout: int
) -> Iterator[BeautifulSoup]:
    """Yield a BeautifulSoup for every page of results, in order."""
    initial = session.get(SEARCH_URL, timeout=timeout)
    initial.raise_for_status()
    form = _hidden_fields(BeautifulSoup(initial.text, "html.parser"))
    form[_SEARCH_FIELD] = query
    form[f"{_BUTTON}.x"] = "10"  # <input type=image> sends the click x/y
    form[f"{_BUTTON}.y"] = "10"
    result = session.post(SEARCH_URL, data=form, timeout=timeout)
    result.raise_for_status()
    soup = BeautifulSoup(result.text, "html.parser")
    yield soup

    visited = {1}
    while len(visited) < _MAX_PAGES:
        available = _pager_targets(soup)
        unvisited = sorted(p for p in available if p not in visited)
        if not unvisited:
            return
        page = unvisited[0]
        form = _hidden_fields(soup)
        form[_SEARCH_FIELD] = query
        form["__EVENTTARGET"] = available[page]
        form["__EVENTARGUMENT"] = ""
        result = session.post(SEARCH_URL, data=form, timeout=timeout)
        result.raise_for_status()
        soup = BeautifulSoup(result.text, "html.parser")
        visited.add(page)
        yield soup


def search_addresses(query: str, *, timeout: int = 30) -> list[AddressOption]:
    """Search for a postcode/address, paging through all results.

    Fast for a precise query (often one page); a bare postcode walks several
    pages but still only the search side, never UPRN resolution.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    options: list[AddressOption] = []
    seen: set[str] = set()
    for soup in _iter_pages(session, query, timeout=timeout):
        for label, _target in _collect_rows(soup):
            if label not in seen:
                seen.add(label)
                options.append(
                    AddressOption(label=label, query=query, index=len(options))
                )
    return options


def resolve_uprn(option: AddressOption, *, timeout: int = 30) -> str | None:
    """Resolve a single chosen address to its UPRN.

    Re-runs the search and pages through results until the matching address is
    found, then clicks its Select link *on that page* (the Select index is only
    valid for the page the address appears on).
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    for soup in _iter_pages(session, option.query, timeout=timeout):
        for label, target in _collect_rows(soup):
            if label != option.label:
                continue
            form = _hidden_fields(soup)
            form[_SEARCH_FIELD] = option.query
            form["__EVENTTARGET"] = target
            form["__EVENTARGUMENT"] = ""
            selected = session.post(
                SEARCH_URL, data=form, timeout=timeout, allow_redirects=True
            )
            match = _UPRN_RE.search(selected.url) or _UPRN_RE.search(selected.text)
            return match.group(1) if match else None
    return None


if __name__ == "__main__":
    import sys

    term = " ".join(sys.argv[1:]) or "G1 1RX"
    print(f"Searching for {term!r} ...")
    options = search_addresses(term)
    if not options:
        print("No addresses found.")
        raise SystemExit(1)
    print(f"Found {len(options)} address(es):")
    for opt in options:
        print(f"  [{opt.index + 1}] {opt.label}")
