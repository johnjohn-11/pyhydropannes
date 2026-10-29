"""Async client for Hydro-Québec's Info-pannes outage service."""

from .client import HydroPannesClient, normalize_postal_code, validate_location_id
from .exceptions import (
    HydroPannesAmbiguousAddressError,
    HydroPannesConnectionError,
    HydroPannesError,
    HydroPannesInvalidLocationIdError,
    HydroPannesInvalidPostalCodeError,
    HydroPannesInvalidResponseError,
    HydroPannesLocationNotFoundError,
    HydroPannesServerError,
    HydroPannesStatusError,
    HydroPannesTimeoutError,
)
from .model import (
    Interruption,
    Location,
    LocationState,
    missing_root_fields,
    parse_datetime,
    round_up_quarter,
    unknown_interruption_fields,
    unknown_root_fields,
)

__all__ = [
    "HydroPannesAmbiguousAddressError",
    "HydroPannesClient",
    "HydroPannesConnectionError",
    "HydroPannesError",
    "HydroPannesInvalidLocationIdError",
    "HydroPannesInvalidPostalCodeError",
    "HydroPannesInvalidResponseError",
    "HydroPannesLocationNotFoundError",
    "HydroPannesServerError",
    "HydroPannesStatusError",
    "HydroPannesTimeoutError",
    "Interruption",
    "Location",
    "LocationState",
    "missing_root_fields",
    "normalize_postal_code",
    "parse_datetime",
    "round_up_quarter",
    "unknown_interruption_fields",
    "unknown_root_fields",
    "validate_location_id",
]
