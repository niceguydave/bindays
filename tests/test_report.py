"""Unit tests for the CLI's pure helpers: reporting and config resolution."""

import datetime
import json

import pytest

import bin_check
from tests.helpers import make_collection

TODAY = datetime.date(2026, 6, 1)


def _sample_collections():
    return [
        make_collection(month=6, day=5, bin="brown"),
        make_collection(month=6, day=12, bin="blue"),
        make_collection(month=6, day=12, bin="green"),
        make_collection(month=7, day=3, bin="grey"),  # outside a 4-week window
    ]


class TestUpcoming:
    def test_filters_to_window(self):
        result = bin_check.upcoming(_sample_collections(), weeks=4, today=TODAY)

        assert datetime.date(2026, 7, 3) not in {c.date for c in result}
        assert datetime.date(2026, 6, 5) in {c.date for c in result}

    def test_excludes_past_dates(self):
        past = [make_collection(month=5, day=1, bin="brown")]
        assert bin_check.upcoming(past, weeks=4, today=TODAY) == []


class TestFormatReport:
    def test_headline_and_grouping(self):
        report = bin_check.format_report(_sample_collections(), weeks=4, today=TODAY)

        assert "Next collection:" in report
        assert "BROWN" in report.splitlines()[0]
        assert "BLUE, GREEN" in report  # multiple bins on one day grouped + sorted
        assert "Jul" not in report  # filtered out of the 4-week window

    def test_empty_window_message(self):
        report = bin_check.format_report([], weeks=4, today=TODAY)
        assert "No collections found" in report


@pytest.mark.parametrize(
    "delta, expected",
    [
        (datetime.timedelta(seconds=30), "just now"),
        (datetime.timedelta(minutes=10), "10 minutes ago"),
        (datetime.timedelta(hours=5), "5 hours ago"),
        (datetime.timedelta(days=3), "3 days ago"),
    ],
)
def test_humanise_age(delta, expected):
    now = datetime.datetime(2026, 6, 1, 12, 0, 0)
    assert bin_check._humanise_age(now - delta, now) == expected


class TestResolveConfiguredUprn:
    def test_cli_argument_wins(self, monkeypatch):
        monkeypatch.setenv("BINDAYS_UPRN", "from-env")
        assert bin_check.resolve_configured_uprn("from-cli") == ("from-cli", None)

    def test_env_var_beats_config(self, monkeypatch, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"uprn": "from-config", "address": "X"}))
        monkeypatch.setattr(bin_check, "CONFIG_PATH", cfg)
        monkeypatch.setenv("BINDAYS_UPRN", "from-env")

        assert bin_check.resolve_configured_uprn(None) == ("from-env", None)

    def test_falls_back_to_saved_config(self, monkeypatch, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"uprn": "from-config", "address": "12 Foo St"}))
        monkeypatch.setattr(bin_check, "CONFIG_PATH", cfg)
        monkeypatch.delenv("BINDAYS_UPRN", raising=False)

        assert bin_check.resolve_configured_uprn(None) == ("from-config", "12 Foo St")

    def test_nothing_configured(self, monkeypatch, tmp_path):
        monkeypatch.setattr(bin_check, "CONFIG_PATH", tmp_path / "missing.json")
        monkeypatch.delenv("BINDAYS_UPRN", raising=False)

        assert bin_check.resolve_configured_uprn(None) == (None, None)
