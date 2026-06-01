"""bindays - tells you which bins go out and when.

Currently supports **only Glasgow City Council**. The design keeps all
council-specific code behind a single seam so other councils can be added later:

  * ``models``   - shared data types (``Collection``, ``AddressOption``).
  * ``council``  - the ``Council`` provider interface (no council specifics).
  * ``councils`` - concrete providers + the ``SUPPORTED_COUNCILS`` registry.
                   Today: only ``councils.glasgow``.
  * ``cache``    - council-agnostic caching of parsed results.

Everything else (the CLI, future web/voice interfaces) is built on top of the
plain list of events a council provider returns.
"""

from .council import Council
from .councils import (
    DEFAULT_COUNCIL,
    SUPPORTED_COUNCILS,
    GlasgowCityCouncil,
    get_council,
)
from .models import AddressOption, Collection

__all__ = [
    "Collection",
    "AddressOption",
    "Council",
    "GlasgowCityCouncil",
    "SUPPORTED_COUNCILS",
    "DEFAULT_COUNCIL",
    "get_council",
]
