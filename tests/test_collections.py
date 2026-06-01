"""Unit tests for the data layer: parsing and fetching collection calendars."""

import datetime

import pytest

from bindays.councils.glasgow import calendar as mod
from bindays.councils.glasgow.calendar import (
    PRINT_CALENDAR_URL,
    get_collections,
    parse_calendar_html,
)
from bindays.models import Collection
from tests.helpers import build_calendar_html


class TestParseCalendarHtml:
    def test_extracts_dates_and_bins(self):
        html = build_calendar_html(
            [
                ("June", 5, ["brown"]),
                ("June", 12, ["blue"]),
            ]
        )

        result = parse_calendar_html(html, today=datetime.date(2026, 6, 1))

        assert result == [
            Collection(datetime.date(2026, 6, 5), "brown"),
            Collection(datetime.date(2026, 6, 12), "blue"),
        ]

    def test_multiple_bins_on_one_day(self):
        html = build_calendar_html([("June", 19, ["brown", "green"])])

        result = parse_calendar_html(html, today=datetime.date(2026, 6, 1))

        assert {c.bin for c in result} == {"brown", "green"}
        assert all(c.date == datetime.date(2026, 6, 19) for c in result)

    def test_deduplicates_and_sorts(self):
        # Arrange: same bin listed twice, and months out of order.
        html = build_calendar_html(
            [
                ("July", 3, ["brown"]),
                ("June", 5, ["brown", "brown"]),
            ]
        )

        result = parse_calendar_html(html, today=datetime.date(2026, 6, 1))

        assert result == [
            Collection(datetime.date(2026, 6, 5), "brown"),
            Collection(datetime.date(2026, 7, 3), "brown"),
        ]

    def test_ignores_unknown_bin_colours(self):
        html = build_calendar_html([("June", 5, ["turquoise"])])

        assert parse_calendar_html(html, today=datetime.date(2026, 6, 1)) == []

    def test_empty_page_returns_empty_list(self):
        assert (
            parse_calendar_html(
                "<html><body></body></html>", today=datetime.date(2026, 6, 1)
            )
            == []
        )

    def test_year_rollover_december_to_january(self):
        # In late December, a "January" entry belongs to next year.
        html = build_calendar_html(
            [
                ("December", 27, ["green"]),
                ("January", 5, ["brown"]),
            ]
        )

        result = parse_calendar_html(html, today=datetime.date(2026, 12, 20))

        assert Collection(datetime.date(2026, 12, 27), "green") in result
        assert Collection(datetime.date(2027, 1, 5), "brown") in result


@pytest.mark.parametrize(
    "month, day, today, expected",
    [
        (6, 5, datetime.date(2026, 6, 1), datetime.date(2026, 6, 5)),
        (1, 5, datetime.date(2026, 12, 20), datetime.date(2027, 1, 5)),  # rollover
        (2, 30, datetime.date(2026, 1, 1), None),  # invalid day
    ],
)
def test_resolve_date(month, day, today, expected):
    assert mod._resolve_date(month, day, today) == expected


class TestCollection:
    def test_description_for_known_and_unknown_bins(self):
        assert "Glass" in Collection(datetime.date(2026, 6, 5), "purple").description
        assert (
            Collection(datetime.date(2026, 6, 5), "mystery").description
            == "Unknown bin"
        )


class TestGetCollections:
    def test_fetches_and_parses(self, requests_mock):
        uprn = "123456789012"
        html = build_calendar_html([("June", 5, ["brown"])])
        requests_mock.get(PRINT_CALENDAR_URL + uprn, text=html)

        result = get_collections(uprn)

        assert (
            Collection(datetime.date(datetime.date.today().year, 6, 5), "brown")
            in result
        )

    def test_raises_on_http_error(self, requests_mock):
        uprn = "123456789012"
        requests_mock.get(PRINT_CALENDAR_URL + uprn, status_code=500)

        with pytest.raises(Exception):
            get_collections(uprn)
