"""Factory helpers for tests.

Following the book's advice to prefer small *factory functions* over heavyweight
fixture files: these build exactly the data a test needs, close to the test.

``build_calendar_html`` produces HTML shaped like the council's PrintCalendar
page, so we can exercise the real parser without ever touching the network.
"""

import datetime
from collections import defaultdict

from bindays.models import Collection


def make_collection(
    year: int = 2026, month: int = 6, day: int = 5, bin: str = "brown"
) -> Collection:
    return Collection(date=datetime.date(year, month, day), bin=bin)


def build_calendar_html(entries: list[tuple[str, int, list[str]]]) -> str:
    """Build council-style calendar HTML.

    ``entries`` is a list of ``(month_name, day, [bin_colours])`` tuples, e.g.
    ``[("June", 5, ["brown"]), ("June", 12, ["blue", "green"])]``.

    Mirrors the structure the parser looks for: one ``<table id="<Month>_Calendar">``
    per month, day cells of class ``calendar-day`` containing an inner
    ``<td align="right">DAY</td>`` plus an ``<img alt="... <colour> ...">`` per bin.
    """
    by_month: dict[str, list[tuple[int, list[str]]]] = defaultdict(list)
    for month_name, day, bins in entries:
        by_month[month_name].append((day, bins))

    tables = []
    for month_name, days in by_month.items():
        cells = []
        for day, bins in days:
            imgs = "".join(
                f'<img alt="{colour} bin collection" src="bin.png"/>' for colour in bins
            )
            cells.append(
                '<td class="calendar-day">'
                f'<table><tr><td align="right">{day}</td></tr></table>{imgs}'
                "</td>"
            )
        tables.append(
            f'<table id="{month_name}_Calendar"><tr>{"".join(cells)}</tr></table>'
        )
    return "<html><body>" + "".join(tables) + "</body></html>"
