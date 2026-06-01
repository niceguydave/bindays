"""Glasgow data layer: fetch and parse the council's bin collection calendars.

This module is **Glasgow-specific** (its URL and HTML parsing). It is one half of
the Glasgow provider in ``bindays.councils.glasgow``; other councils would supply
their own equivalent. See ``bindays.council`` for the interface and the current
single-council limitation.


The council has no official API. Instead, each property has a 12-digit UPRN
(Unique Property Reference Number), and the collection calendar for that UPRN is
served as an HTML page:

    https://onlineservices.glasgow.gov.uk/forms/refuseandrecyclingcalendar/PrintCalendar.aspx?UPRN=<uprn>

The page contains one HTML table per month (``id="January_Calendar"`` etc.). Each
day cell holds zero or more ``<img>`` tags whose ``alt`` text names the bin that
is collected that day (blue/green/grey/purple/brown).

This module turns that messy HTML into a clean, sorted list of ``Collection``
records. Every higher layer (printing, querying, voice) works off that list, so
this is the only place that knows about the council's HTML format.
"""

import datetime

import requests
from bs4 import BeautifulSoup, Tag

from ...models import KNOWN_BINS, Collection

PRINT_CALENDAR_URL = (
    "https://onlineservices.glasgow.gov.uk/forms/"
    "refuseandrecyclingcalendar/PrintCalendar.aspx?UPRN="
)

# Some servers reject requests without a browser-like User-Agent.
HEADERS = {"User-Agent": "Mozilla/5.0 (bindays)"}

_MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def fetch_calendar_html(uprn: str, *, timeout: int = 15) -> str:
    """Fetch the raw calendar HTML for a UPRN. Raises on network/HTTP errors."""
    response = requests.get(PRINT_CALENDAR_URL + uprn, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


def parse_calendar_html(
    html: str, *, today: datetime.date | None = None
) -> list[Collection]:
    """Parse calendar HTML into a sorted list of ``Collection`` records.

    ``today`` is injectable so the year-rollover logic can be unit tested. The
    council page labels months by name only (no year), so we infer the year:
    a month/day that would land more than ~30 days in the past is assumed to
    belong to next year (handles the December -> January boundary).
    """
    today = today or datetime.date.today()
    soup = BeautifulSoup(html, "html.parser")
    collections: list[Collection] = []

    for month_index, month_name in enumerate(_MONTHS, start=1):
        table = soup.find("table", id=f"{month_name}_Calendar")
        if not isinstance(table, Tag):
            continue

        for cell in table.find_all("td", class_="calendar-day"):
            day_label = cell.find("td", attrs={"align": "right"})
            if day_label is None or not day_label.text.strip().isdigit():
                continue
            day = int(day_label.text.strip())

            date = _resolve_date(month_index, day, today)
            if date is None:
                continue

            for img in cell.find_all("img"):
                alt = img.get("alt", "").lower()
                for colour in KNOWN_BINS:
                    if colour in alt:
                        collections.append(Collection(date=date, bin=colour))

    # De-duplicate (a day might list a bin more than once) and sort.
    return sorted(set(collections))


def get_collections(uprn: str, *, timeout: int = 15) -> list[Collection]:
    """Fetch and parse the collection calendar for a UPRN."""
    html = fetch_calendar_html(uprn, timeout=timeout)
    return parse_calendar_html(html)


def _resolve_date(month: int, day: int, today: datetime.date) -> datetime.date | None:
    """Attach a sensible year to a (month, day) from the calendar page."""
    for year in (today.year, today.year + 1):
        try:
            candidate = datetime.date(year, month, day)
        except ValueError:
            return None  # invalid day for this month
        if candidate >= today - datetime.timedelta(days=30):
            return candidate
    return datetime.date(today.year, month, day)
