"""Local cache for parsed collection calendars.

The council's schedule changes rarely (once or twice a year), but fetching and
parsing it hits a slow server every time. So after the first fetch we store the
parsed events in a small JSON file and serve from there. We only re-fetch when
the cache is older than ``max_age`` (default 7 days) or the caller forces it.

Bonus resilience: if a refresh fails (server down/slow) but we still have a
cached copy, we fall back to it rather than failing - you always get an answer.
"""

import datetime
import json
from dataclasses import dataclass
from pathlib import Path

from .council import CollectionsFetcher
from .models import Collection

DEFAULT_MAX_AGE = datetime.timedelta(days=7)


@dataclass
class CollectionsResult:
    collections: list[Collection]
    fetched_at: datetime.datetime
    from_cache: bool
    stale: bool = False  # True when we served an out-of-date cache as a fallback


def _serialise(collection: Collection) -> dict:
    return {"date": collection.date.isoformat(), "bin": collection.bin}


def _deserialise(raw: dict) -> Collection:
    return Collection(date=datetime.date.fromisoformat(raw["date"]), bin=raw["bin"])


def _read_cache(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(
    path: Path, uprn: str, collections: list[Collection], fetched_at: datetime.datetime
) -> None:
    payload = {
        "uprn": uprn,
        "fetched_at": fetched_at.isoformat(),
        "collections": [_serialise(c) for c in collections],
    }
    try:
        path.write_text(json.dumps(payload, indent=2))
    except OSError:
        pass  # caching is best-effort; never block on a write failure


def _load_for_uprn(
    path: Path, uprn: str
) -> tuple[list[Collection], datetime.datetime] | None:
    """Return (collections, fetched_at) from cache if it matches this UPRN."""
    data = _read_cache(path)
    if not data or data.get("uprn") != uprn:
        return None
    try:
        fetched_at = datetime.datetime.fromisoformat(data["fetched_at"])
        collections = [_deserialise(c) for c in data["collections"]]
    except (KeyError, ValueError):
        return None
    return collections, fetched_at


def get_collections_cached(
    uprn: str,
    *,
    fetch: CollectionsFetcher,
    cache_path: Path,
    max_age: datetime.timedelta = DEFAULT_MAX_AGE,
    force_refresh: bool = False,
    now: datetime.datetime | None = None,
) -> CollectionsResult:
    """Return collections for a UPRN, using the local cache when fresh.

    ``fetch`` is the council-specific function that retrieves and parses a
    schedule (e.g. a provider's ``get_collections``). Requiring it as an argument
    keeps this cache council-agnostic - it never imports a specific council.

    Order of operations:
      1. If not forcing a refresh and the cache is fresh, return it (instant).
      2. Otherwise. fetch and parse from the council, then update the cache.
      3. If that fetch fails, but we have *any* cached copy, return it as stale.
    """
    now = now or datetime.datetime.now()
    cached = _load_for_uprn(cache_path, uprn)

    if not force_refresh and cached is not None:
        collections, fetched_at = cached
        if now - fetched_at < max_age:
            return CollectionsResult(collections, fetched_at, from_cache=True)

    try:
        fresh = fetch(uprn)
    except Exception:
        if cached is not None:  # network/server problem -> fall back to old data
            collections, fetched_at = cached
            return CollectionsResult(
                collections, fetched_at, from_cache=True, stale=True
            )
        raise

    _write_cache(cache_path, uprn, fresh, now)
    return CollectionsResult(fresh, now, from_cache=False)
