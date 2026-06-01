"""Shared, council-agnostic data types.

These are the plain data structures every layer speaks in. They deliberately
contain no council-specific behaviour (no URLs, no HTML), so any council provider
can produce them and the CLI/cache can consume them.
"""

import datetime
from dataclasses import dataclass

# The kerbside bins, keyed by the short colour word a council uses to identify
# them. This default mapping reflects Glasgow's scheme; a future council with a
# different colour scheme can override the descriptions in its own provider.
KNOWN_BINS = {
    "blue": "Paper, card, cans and plastic bottles",
    "green": "General (non-recyclable) waste",
    "grey": "Food waste",
    "purple": "Glass",
    "brown": "Garden waste (and food via compostable liners)",
}


@dataclass(frozen=True, order=True)
class Collection:
    """A single bin collection on a single day.

    ``order=True`` plus putting ``date`` first means a list of Collections sorts
    chronologically out of the box.
    """

    date: datetime.date
    bin: str  # one of the keys in KNOWN_BINS, e.g. "brown"

    @property
    def description(self) -> str:
        return KNOWN_BINS.get(self.bin, "Unknown bin")


@dataclass(frozen=True)
class AddressOption:
    """One address in a council's search results, not yet resolved to a UPRN.

    ``query`` is the original search term, kept so a provider can re-run the
    search when resolving the chosen address.
    """

    label: str
    query: str
    index: int
