"""Council providers and the registry of which councils are supported.

Today there is exactly one provider: Glasgow. To add another council, implement
the ``Council`` protocol (see ``bindays.council``) as a new subpackage here and
register it in ``SUPPORTED_COUNCILS`` below - nothing else needs to change.
"""

from ..council import Council
from .glasgow import GlasgowCityCouncil

# The single source of truth for which councils are supported.
SUPPORTED_COUNCILS: dict[str, Council] = {
    "glasgow": GlasgowCityCouncil(),
}

# Until council selection is offered to users, everything uses Glasgow.
DEFAULT_COUNCIL = "glasgow"


def get_council(key: str = DEFAULT_COUNCIL) -> Council:
    """Return a supported council provider by key.

    Raises ``KeyError`` with a clear message for unsupported councils, which makes
    the current single-council limitation explicit at the point of use.
    """
    try:
        return SUPPORTED_COUNCILS[key]
    except KeyError:
        supported = ", ".join(sorted(SUPPORTED_COUNCILS))
        raise KeyError(
            f"Council {key!r} is not supported. Supported councils: {supported}."
        ) from None


__all__ = [
    "SUPPORTED_COUNCILS",
    "DEFAULT_COUNCIL",
    "get_council",
    "GlasgowCityCouncil",
]
