"""The council provider interface - the seam for (currently) one council.

IMPORTANT: this project currently supports **only Glasgow City Council (GCC)**.

Every council publishes bin data differently (some have JSON APIs, some need
scraping, some don't use UPRNs at all). All of that council-specific knowledge
lives behind the ``Council`` interface defined here. The rest of the app (the
CLI, the cache) talks only to a ``Council`` object, never to a council directly.

Concrete providers live under ``bindays.councils`` (today: only ``glasgow``).
``bindays.councils.get_council`` returns one and lists what's supported.
"""

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from .models import AddressOption, Collection


@runtime_checkable
class Council(Protocol):
    """The operations any supported council must provide.

    A future council provider just needs to implement these members. How it does
    so (API call, HTML scrape, ...) is entirely its own business.
    """

    # Read-only properties so immutable (frozen) providers satisfy the protocol.
    @property
    def key(self) -> str:
        """Short identifier, e.g. "glasgow"."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name, e.g. "Glasgow City Council"."""
        ...

    @property
    def website(self) -> str:
        """The public page this provider is built on."""
        ...

    @property
    def attribution(self) -> str:
        """A short, user-facing credit for the council as the data source."""
        ...

    def find_addresses(self, query: str) -> list[AddressOption]:
        """Search for addresses matching a postcode/street."""
        ...

    def resolve_uprn(self, option: AddressOption) -> str | None:
        """Resolve a chosen address to its UPRN (or None)."""
        ...

    def get_collections(self, uprn: str) -> list[Collection]:
        """Fetch the collection schedule for a property."""
        ...


# The type of a council's collection fetcher, used by the (council-agnostic)
# cache so it never has to import a specific council.
CollectionsFetcher = Callable[[str], list[Collection]]

__all__ = ["Council", "CollectionsFetcher"]
