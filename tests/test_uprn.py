"""Unit tests for the address-search / UPRN-resolution layer.

The council search is an ASP.NET WebForms flow (load -> search -> page -> select).
We drive the whole multi-step flow through requests-mock, so these tests never
hit the network yet still exercise the real pagination and select logic.
"""

from bs4 import BeautifulSoup

from bindays.councils.glasgow import uprn as mod
from bindays.councils.glasgow.uprn import (
    SEARCH_URL,
    _collect_rows,
    _hidden_fields,
    _pager_targets,
    resolve_uprn,
    search_addresses,
)
from bindays.models import AddressOption

PREFIX = "ctl00$Application$Addresses"


def _hidden_inputs() -> str:
    return (
        '<input name="__VIEWSTATE" value="vs"/>'
        '<input name="__EVENTVALIDATION" value="ev"/>'
    )


def _address_row(select_index: int, label: str) -> str:
    target = f"{PREFIX}$Select{select_index}"
    return (
        "<tr>"
        f"<td><a href=\"javascript:__doPostBack('{target}','')\">Select</a></td>"
        f"<td>{label}</td>"
        "</tr>"
    )


def _pager_link(page: int) -> str:
    target = f"{PREFIX}$Page{page}"
    return f"<a href=\"javascript:__doPostBack('{target}','')\">{page}</a>"


def _page(rows: str, pager: str = "") -> str:
    return (
        f"<html><body><form>{_hidden_inputs()}"
        f"<table>{rows}</table>{pager}</form></body></html>"
    )


class TestParsingHelpers:
    def test_hidden_fields_reads_tokens_and_defaults_missing(self):
        soup = BeautifulSoup(_hidden_inputs(), "html.parser")

        fields = _hidden_fields(soup)

        assert fields["__VIEWSTATE"] == "vs"
        assert fields["__EVENTVALIDATION"] == "ev"
        assert fields["__EVENTTARGET"] == ""  # missing input -> empty default

    def test_collect_rows_skips_pager_and_digit_labels(self):
        rows = (
            _address_row(0, "1 A Street, Glasgow, G1 1RX")
            + _address_row(1, "123")  # pure-digit label = pager artefact, skip
        )
        soup = BeautifulSoup(_page(rows, _pager_link(2)), "html.parser")

        collected = _collect_rows(soup)

        assert [label for label, _ in collected] == ["1 A Street, Glasgow, G1 1RX"]

    def test_pager_targets_maps_page_numbers(self):
        soup = BeautifulSoup(_page("", _pager_link(2) + _pager_link(3)), "html.parser")

        assert set(_pager_targets(soup).keys()) == {2, 3}


class TestSearchAddresses:
    def test_pages_through_all_results(self, requests_mock):
        form = _page("")
        page1 = _page(
            _address_row(0, "1 A Street") + _address_row(1, "2 B Street"),
            pager=_pager_link(2),
        )
        page2 = _page(_address_row(0, "3 C Street"))  # no pager -> last page

        requests_mock.get(SEARCH_URL, text=form)
        requests_mock.post(SEARCH_URL, [{"text": page1}, {"text": page2}])

        options = search_addresses("G1 1RX")

        assert [o.label for o in options] == ["1 A Street", "2 B Street", "3 C Street"]


class TestResolveUprn:
    def test_resolves_address_on_a_later_page(self, requests_mock):
        form = _page("")
        page1 = _page(_address_row(0, "1 A Street"), pager=_pager_link(2))
        page2 = _page(_address_row(0, "105 Target Street"))
        # The select postback "redirects" to the calendar URL carrying the UPRN.
        select_result = (
            '<html><body><a href="PrintCalendar.aspx?UPRN=900000000001">'
            "calendar</a></body></html>"
        )

        requests_mock.get(SEARCH_URL, text=form)
        requests_mock.post(
            SEARCH_URL,
            [{"text": page1}, {"text": page2}, {"text": select_result}],
        )

        option = AddressOption(label="105 Target Street", query="G1 1RX", index=0)
        assert resolve_uprn(option) == "900000000001"

    def test_returns_none_when_address_not_found(self, requests_mock):
        requests_mock.get(SEARCH_URL, text=_page(""))
        requests_mock.post(SEARCH_URL, text=_page(_address_row(0, "Some Other Street")))

        option = AddressOption(label="Nonexistent Street", query="G1 1RX", index=0)
        assert resolve_uprn(option) is None


def test_uprn_regex_matches_uppercase_and_query_param():
    assert mod._UPRN_RE.search("foo?UPRN=906700119667&x=1").group(1) == "906700119667"
