#!/usr/bin/env python3
"""Iteration 0 CLI for Glasgow bin collections.

First time only - find and save your property:

    python bin_check.py setup            # asks for your postcode, then saves your UPRN
    python bin_check.py setup "G1 1RX"    # or pass the postcode directly

After that, just check your bins:

    python bin_check.py                  # next 4 weeks
    python bin_check.py --weeks 8        # look further ahead

How your property is found (in priority order):
    1. --uprn on the command line
    2. the BINDAYS_UPRN environment variable
    3. the saved config from `setup` (config.json next to this script)
"""

import argparse
import datetime
import itertools
import json
import os
import sys
from pathlib import Path

from bindays import Collection, get_council
from bindays.cache import get_collections_cached

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
CACHE_PATH = Path(__file__).resolve().parent / "cache.json"


# --------------------------------------------------------------------------- #
# Config persistence (so end users don't juggle environment variables)
# --------------------------------------------------------------------------- #
def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(uprn: str, address: str) -> None:
    CONFIG_PATH.write_text(json.dumps({"uprn": uprn, "address": address}, indent=2))


def resolve_configured_uprn(cli_uprn: str | None) -> tuple[str | None, str | None]:
    """Return (uprn, address_label) using CLI > env var > saved config."""
    if cli_uprn:
        return cli_uprn, None
    env = os.environ.get("BINDAYS_UPRN")
    if env:
        return env, None
    cfg = load_config()
    return cfg.get("uprn"), cfg.get("address")


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def upcoming(
    collections: list[Collection], *, weeks: int, today: datetime.date
) -> list[Collection]:
    horizon = today + datetime.timedelta(weeks=weeks)
    return [c for c in collections if today <= c.date <= horizon]


def format_report(
    collections: list[Collection], *, weeks: int, today: datetime.date
) -> str:
    coming = upcoming(collections, weeks=weeks, today=today)
    if not coming:
        return f"No collections found in the next {weeks} weeks."

    lines: list[str] = []
    next_date = coming[0].date
    next_bins = [c.bin for c in coming if c.date == next_date]
    days_away = (next_date - today).days
    when = (
        "today"
        if days_away == 0
        else "tomorrow"
        if days_away == 1
        else f"in {days_away} days"
    )
    lines.append(
        f"Next collection: {', '.join(b.upper() for b in next_bins)} "
        f"on {next_date:%A %-d %B} ({when})."
    )
    lines.append("")
    lines.append(f"Upcoming collections (next {weeks} weeks):")
    for date, group in itertools.groupby(coming, key=lambda c: c.date):
        bins = ", ".join(c.bin.upper() for c in group)
        lines.append(f"  {date:%a %d %b %Y}  -  {bins}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_setup(query: str | None) -> int:
    council = get_council()  # only Glasgow City Council today (see council.py)
    if not query:
        query = input("Enter your postcode or address (e.g. G1 1RX): ").strip()
    if not query:
        print("Nothing entered.", file=sys.stderr)
        return 1

    print(
        f"Searching {council.name} for {query!r} (this can take ~10 seconds)...",
        file=sys.stderr,
        flush=True,
    )
    try:
        options = council.find_addresses(query)
    except Exception as exc:
        print(f"Address search failed: {exc}", file=sys.stderr)
        return 1

    if not options:
        print(
            'No addresses found. Try a more specific search, e.g. "231 George Street".',
            file=sys.stderr,
        )
        return 1

    if len(options) == 1:
        chosen = options[0]
    else:
        print(f"\nFound {len(options)} addresses:")
        for opt in options:
            print(f"  [{opt.index + 1}] {opt.label}")
        try:
            picked = int(input(f"\nWhich one is yours? [1-{len(options)}]: ").strip())
        except (ValueError, EOFError):
            print("Invalid choice.", file=sys.stderr)
            return 1
        if not 1 <= picked <= len(options):
            print("Choice out of range.", file=sys.stderr)
            return 1
        chosen = options[picked - 1]

    print(
        f"Looking up UPRN for {chosen.label!r} (a few more seconds)...",
        file=sys.stderr,
        flush=True,
    )
    try:
        uprn = council.resolve_uprn(chosen)
    except Exception as exc:
        print(f"UPRN lookup failed: {exc}", file=sys.stderr)
        return 1
    if not uprn:
        print("Could not determine the UPRN for that address.", file=sys.stderr)
        return 1

    save_config(uprn, chosen.label)
    print(f"\nSaved {chosen.label}")
    print(f"UPRN {uprn} -> {CONFIG_PATH.name}")
    print("\nDone! Now just run:  python bin_check.py")
    print(f"\n{council.attribution}", file=sys.stderr)
    return 0


def _humanise_age(fetched_at: datetime.datetime, now: datetime.datetime) -> str:
    seconds = (now - fetched_at).total_seconds()
    if seconds < 90:
        return "just now"
    minutes = seconds / 60
    if minutes < 90:
        return f"{round(minutes)} minutes ago"
    hours = minutes / 60
    if hours < 36:
        return f"{round(hours)} hours ago"
    return f"{round(hours / 24)} days ago"


def cmd_show(
    cli_uprn: str | None, weeks: int, *, refresh: bool, max_age_days: int
) -> int:
    council = get_council()  # only Glasgow City Council today (see council.py)
    uprn, address = resolve_configured_uprn(cli_uprn)
    if not uprn:
        print(
            "No property configured yet.\nRun this once:  python bin_check.py setup",
            file=sys.stderr,
        )
        return 1

    if address:
        print(f"{address}", file=sys.stderr)

    # Only the slow path (an actual fetch) prints progress; cache hits are instant.
    needs_fetch = refresh or not _cache_is_fresh(uprn, max_age_days)
    if needs_fetch:
        print("Fetching collection calendar...", file=sys.stderr, flush=True)

    now = datetime.datetime.now()
    try:
        result = get_collections_cached(
            uprn,
            cache_path=CACHE_PATH,
            max_age=datetime.timedelta(days=max_age_days),
            force_refresh=refresh,
            now=now,
            fetch=council.get_collections,
        )
    except Exception as exc:
        print(f"Could not retrieve collections: {exc}", file=sys.stderr)
        return 1

    if not result.collections:
        print(
            "No collection data found. Double-check the UPRN is correct.",
            file=sys.stderr,
        )
        return 1

    if result.from_cache:
        note = f"cached, updated {_humanise_age(result.fetched_at, now)}"
        if result.stale:
            note += "; council site unreachable, showing last known data"
        else:
            note += "; use --refresh to update"
        print(f"({note})", file=sys.stderr)

    print(format_report(result.collections, weeks=weeks, today=datetime.date.today()))
    return 0


def _cache_is_fresh(uprn: str, max_age_days: int) -> bool:
    """Cheap check used only to decide whether to print the 'Fetching...' note."""
    from bindays.cache import _load_for_uprn  # internal helper, fine here

    cached = _load_for_uprn(CACHE_PATH, uprn)
    if cached is None:
        return False
    _collections, fetched_at = cached
    return datetime.datetime.now() - fetched_at < datetime.timedelta(days=max_age_days)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Glasgow bin collection lookup (Iteration 0)"
    )
    sub = parser.add_subparsers(dest="command")

    setup_p = sub.add_parser("setup", help="find and save your property (run once)")
    setup_p.add_argument("query", nargs="?", help="postcode or address to search for")

    # Default command (no subcommand) shows upcoming collections.
    parser.add_argument("--uprn", default=None, help="override the saved/env UPRN")
    parser.add_argument(
        "--weeks", type=int, default=4, help="weeks ahead to list (default 4)"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="force a re-fetch from the council, ignoring the cache",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=7,
        help="re-fetch if the cache is older than this (default 7)",
    )
    args = parser.parse_args(argv)

    if args.command == "setup":
        return cmd_setup(args.query)
    return cmd_show(
        args.uprn, args.weeks, refresh=args.refresh, max_age_days=args.max_age_days
    )


if __name__ == "__main__":
    raise SystemExit(main())
