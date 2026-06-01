"""Glasgow City Council provider - the only council implemented today.

This subpackage holds everything specific to Glasgow:
  * ``calendar`` - fetch + parse the council's HTML collection calendar.
  * ``uprn`` - resolve a postcode/address to a UPRN via the council's search.

The ``GlasgowCityCouncil`` class below is a thin adapter that exposes those as
the council-agnostic ``Council`` interface (see ``bindays.council``).
"""

from dataclasses import dataclass

from ...models import AddressOption, Collection
from .calendar import get_collections
from .uprn import resolve_uprn, search_addresses


@dataclass(frozen=True)
class GlasgowCityCouncil:
    key: str = "glasgow"
    name: str = "Glasgow City Council"
    website: str = "https://www.glasgow.gov.uk/article/1524/Bin-Collection-Days"
    attribution: str = (
        "Bin collection data from Glasgow City Council "
        "(https://www.glasgow.gov.uk/article/1524/Bin-Collection-Days). "
        "This is an unofficial tool, not affiliated with or endorsed by the council."
    )

    def find_addresses(self, query: str) -> list[AddressOption]:
        return search_addresses(query)

    def resolve_uprn(self, option: AddressOption) -> str | None:
        return resolve_uprn(option)

    def get_collections(self, uprn: str) -> list[Collection]:
        return get_collections(uprn)


__all__ = ["GlasgowCityCouncil"]
