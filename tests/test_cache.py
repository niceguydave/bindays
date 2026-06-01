"""Unit tests for the caching layer.

We inject ``now`` for deterministic time control (the book's "mock time"
principle) and inject ``fetch`` so these tests never touch the network and can
count how often a real fetch would happen. Injecting the fetcher (rather than
patching a global) mirrors how the cache is used: it's council-agnostic and the
caller supplies the provider's ``get_collections``.
"""

import datetime

import pytest

from bindays.cache import get_collections_cached
from tests.helpers import make_collection

T0 = datetime.datetime(2026, 6, 1, 9, 0, 0)


@pytest.fixture
def cache_path(tmp_path):
    return tmp_path / "cache.json"


@pytest.fixture
def fake_fetch():
    """A counter-backed fake fetcher, used as the injected ``fetch``."""
    calls = {"count": 0}

    def fetch(uprn):
        calls["count"] += 1
        return [make_collection(day=5, bin="brown")]

    calls["fn"] = fetch
    return calls


def test_cold_cache_fetches_and_writes(cache_path, fake_fetch):
    result = get_collections_cached(
        "uprn-1", fetch=fake_fetch["fn"], cache_path=cache_path, now=T0
    )

    assert result.from_cache is False
    assert fake_fetch["count"] == 1
    assert cache_path.exists()


def test_warm_cache_served_without_fetching(cache_path, fake_fetch):
    get_collections_cached(
        "uprn-1", fetch=fake_fetch["fn"], cache_path=cache_path, now=T0
    )
    later = T0 + datetime.timedelta(days=1)  # within the 7-day default

    result = get_collections_cached(
        "uprn-1", fetch=fake_fetch["fn"], cache_path=cache_path, now=later
    )

    assert result.from_cache is True
    assert result.stale is False
    assert fake_fetch["count"] == 1  # no second fetch


def test_expired_cache_triggers_refetch(cache_path, fake_fetch):
    get_collections_cached(
        "uprn-1", fetch=fake_fetch["fn"], cache_path=cache_path, now=T0
    )
    much_later = T0 + datetime.timedelta(days=8)  # beyond the 7-day default

    result = get_collections_cached(
        "uprn-1", fetch=fake_fetch["fn"], cache_path=cache_path, now=much_later
    )

    assert result.from_cache is False
    assert fake_fetch["count"] == 2


def test_force_refresh_ignores_fresh_cache(cache_path, fake_fetch):
    get_collections_cached(
        "uprn-1", fetch=fake_fetch["fn"], cache_path=cache_path, now=T0
    )

    result = get_collections_cached(
        "uprn-1",
        fetch=fake_fetch["fn"],
        cache_path=cache_path,
        now=T0,
        force_refresh=True,
    )

    assert result.from_cache is False
    assert fake_fetch["count"] == 2


def test_different_uprn_does_not_use_cache(cache_path, fake_fetch):
    get_collections_cached(
        "uprn-1", fetch=fake_fetch["fn"], cache_path=cache_path, now=T0
    )

    result = get_collections_cached(
        "uprn-2", fetch=fake_fetch["fn"], cache_path=cache_path, now=T0
    )

    assert result.from_cache is False
    assert fake_fetch["count"] == 2


def test_stale_fallback_when_fetch_fails(cache_path):
    # Arrange: seed a valid cache via a working fetch...
    good = [make_collection(day=5, bin="brown")]
    get_collections_cached(
        "uprn-1", fetch=lambda uprn: good, cache_path=cache_path, now=T0
    )

    # ...then make the network fail on a forced refresh.
    def boom(uprn):
        raise RuntimeError("network down")

    result = get_collections_cached(
        "uprn-1", fetch=boom, cache_path=cache_path, now=T0, force_refresh=True
    )

    assert result.from_cache is True
    assert result.stale is True
    assert result.collections == good


def test_raises_when_fetch_fails_and_no_cache(cache_path):
    def boom(uprn):
        raise RuntimeError("network down")

    with pytest.raises(RuntimeError):
        get_collections_cached("uprn-1", fetch=boom, cache_path=cache_path, now=T0)


def test_round_trip_preserves_collections(cache_path, fake_fetch):
    first = get_collections_cached(
        "uprn-1", fetch=fake_fetch["fn"], cache_path=cache_path, now=T0
    )
    second = get_collections_cached(
        "uprn-1",
        fetch=fake_fetch["fn"],
        cache_path=cache_path,
        now=T0 + datetime.timedelta(hours=1),
    )

    assert second.collections == first.collections
