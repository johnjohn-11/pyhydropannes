"""Exceptions raised by pyhydropannes."""

from __future__ import annotations


class HydroPannesError(Exception):
    """Base class for every error raised by this library."""


class HydroPannesConnectionError(HydroPannesError):
    """The service could not be reached, after every retry.

    ``attempts`` is the number of requests made.
    """

    def __init__(self, message: str, *, attempts: int) -> None:
        """Store the number of attempts."""
        super().__init__(message)
        self.attempts = attempts


class HydroPannesTimeoutError(HydroPannesConnectionError):
    """The last attempt timed out."""


class HydroPannesServerError(HydroPannesConnectionError):
    """The last attempt got a 5xx answer."""

    def __init__(self, message: str, *, attempts: int, status: int) -> None:
        """Store the HTTP status of the last attempt."""
        super().__init__(message, attempts=attempts)
        self.status = status


class HydroPannesStatusError(HydroPannesError):
    """The service answered with a status that retrying would not change (4xx, 3xx)."""

    def __init__(self, message: str, *, status: int) -> None:
        """Store the HTTP status."""
        super().__init__(message)
        self.status = status


class HydroPannesInvalidResponseError(HydroPannesError):
    """The service answered 200 with a body this library cannot read."""


class HydroPannesLocationNotFoundError(HydroPannesError):
    """The service knows no consumption location with this number."""


class HydroPannesAmbiguousAddressError(HydroPannesError):
    """The address lookup found several locations it cannot tell apart."""


class HydroPannesInvalidLocationIdError(HydroPannesError, ValueError):
    """The consumption location id is not 10 digits."""


class HydroPannesInvalidPostalCodeError(HydroPannesError, ValueError):
    """The input is not a Canadian postal code."""
