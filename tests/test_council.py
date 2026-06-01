"""Tests for the council provider seam.

These pin down the *current* limitation - only Glasgow is supported - and the
contract a future council provider must satisfy. They are deliberately
network-free: we check the registry and metadata, not live scraping.
"""

import pytest

from bindays import (
    DEFAULT_COUNCIL,
    SUPPORTED_COUNCILS,
    Council,
    GlasgowCityCouncil,
    get_council,
)


def test_only_glasgow_is_supported_today():
    assert set(SUPPORTED_COUNCILS) == {"glasgow"}
    assert DEFAULT_COUNCIL == "glasgow"


def test_default_council_is_glasgow_with_attribution():
    council = get_council()
    assert council.name == "Glasgow City Council"
    assert "glasgow.gov.uk" in council.website
    # The acknowledgement must credit the council and flag the unofficial status.
    assert "Glasgow City Council" in council.attribution
    assert "unofficial" in council.attribution.lower()
    # The data source must be credited, and the unofficial status made clear.
    assert "Glasgow City Council" in council.attribution
    assert "unofficial" in council.attribution.lower()


def test_glasgow_provider_satisfies_the_council_protocol():
    # runtime_checkable Protocol: the provider must expose the full contract.
    assert isinstance(GlasgowCityCouncil(), Council)


def test_unsupported_council_fails_clearly():
    with pytest.raises(KeyError, match="not supported"):
        get_council("edinburgh")
