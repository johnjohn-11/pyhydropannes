"""Async client for the Hydro-Québec Info-pannes API."""

from __future__ import annotations

import asyncio
import logging
import re
from types import TracebackType
from typing import Any, Self

import aiohttp

from .const import API_URL, SEARCH_DUPLICATES_CODE, SEARCH_URL
from .exceptions import (
    HydroPannesAmbiguousAddressError,
    HydroPannesConnectionError,
    HydroPannesInvalidLocationIdError,
    HydroPannesInvalidPostalCodeError,
    HydroPannesInvalidResponseError,
    HydroPannesLocationNotFoundError,
    HydroPannesServerError,
    HydroPannesStatusError,
    HydroPannesTimeoutError,
)
from .model import Location

_LOGGER = logging.getLogger(__name__)

_LOCATION_ID_RE = re.compile(r"^\d{10}$")
_POSTAL_CODE_RE = re.compile(r"^[A-Z]\d[A-Z]\d[A-Z]\d$")

_NOT_JSON = object()


def validate_location_id(location_id: str) -> str:
    """Return the consumption location id stripped, or raise if it is not 10 digits."""
    location_id = location_id.strip()
    if not _LOCATION_ID_RE.match(location_id):
        raise HydroPannesInvalidLocationIdError(location_id)
    return location_id


def normalize_postal_code(postal_code: str) -> str:
    """Return a postal code as ``A1A 1A1``, the only form the lookup accepts.

    Without the space the lookup answers HTTP 500.
    """
    compact = re.sub(r"\s", "", postal_code).upper()
    if not _POSTAL_CODE_RE.match(compact):
        raise HydroPannesInvalidPostalCodeError(postal_code)
    return f"{compact[:3]} {compact[3:]}"


class HydroPannesClient:
    """Client for the public Info-pannes endpoints.

    Pass the application's ``aiohttp.ClientSession``. Without one, the client opens its own and closes it in ``close()``.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession | None = None,
        *,
        request_timeout: float = 10,
        max_retries: int = 2,
        retry_delay: float = 2,
    ) -> None:
        """Set up the client. 5xx answers, timeouts and connection errors are retried ``max_retries`` times."""
        self._session = session
        self._close_session = False
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def _request(self, url: str, params: dict[str, str] | None = None) -> tuple[int, Any]:
        """Return the status and decoded JSON body of a GET, retrying transient failures.

        Any status other than 5xx is returned at once: retrying would not change the answer. The body is ``_NOT_JSON`` when it does not decode.
        """
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._close_session = True

        attempt = 0
        while True:
            attempt += 1
            error: HydroPannesConnectionError
            try:
                async with (
                    asyncio.timeout(self.request_timeout),
                    self._session.get(url, params=params) as response,
                ):
                    if not 500 <= response.status < 600:
                        try:
                            body = await response.json(content_type=None)
                        except ValueError:
                            body = _NOT_JSON
                        return response.status, body
                    error = HydroPannesServerError(
                        f"API returned {response.status} after {attempt} attempts",
                        attempts=attempt,
                        status=response.status,
                    )
            except TimeoutError as err:
                error = HydroPannesTimeoutError(
                    f"Timeout after {attempt} attempts", attempts=attempt
                )
                error.__cause__ = err
            except aiohttp.ClientError as err:
                error = HydroPannesConnectionError(
                    f"Connection error after {attempt} attempts: {err}", attempts=attempt
                )
                error.__cause__ = err

            if attempt > self.max_retries:
                raise error
            _LOGGER.debug("%s, retry %s/%s", error, attempt, self.max_retries)
            # Outside the response context so the connection is released during the wait.
            await asyncio.sleep(self.retry_delay)

    async def async_get_payload(self, location_id: str) -> dict[str, Any]:
        """Return the outage payload of a consumption location, as the API sends it.

        Read it with ``LocationState.from_payload()``. The raw payload is returned so a caller can keep it for diagnostics or check its fields.
        """
        location_id = validate_location_id(location_id)
        status, body = await self._request(API_URL.format(location_id))
        if status != 200:
            raise HydroPannesStatusError(f"API returned status {status}", status=status)
        if body is _NOT_JSON:
            raise HydroPannesInvalidResponseError("API returned a body that is not JSON")
        if isinstance(body, list) and not body:
            raise HydroPannesLocationNotFoundError(location_id)
        if not isinstance(body, list) or not isinstance(body[0], dict):
            raise HydroPannesInvalidResponseError(
                "API returned invalid data format (expected a list of objects)"
            )
        payload: dict[str, Any] = body[0]
        return payload

    async def async_search_locations(
        self, postal_code: str, civic_number: str, apartment: str = ""
    ) -> list[Location]:
        """Look up the eligible consumption locations at an address, one per distinct id.

        The postal code is normalized first. The list can be empty.
        """
        params = {
            "codePostal": normalize_postal_code(postal_code),
            "numeroAppartement": apartment.strip(),
            "numeroCivique": civic_number.strip(),
            "nomRue": "",
        }
        status, body = await self._request(SEARCH_URL, params)
        if status == 400:
            error = body.get("error") if isinstance(body, dict) else None
            if isinstance(error, dict) and error.get("code") == SEARCH_DUPLICATES_CODE:
                raise HydroPannesAmbiguousAddressError
        if status != 200:
            raise HydroPannesStatusError(f"Lookup returned status {status}", status=status)
        if not isinstance(body, list):
            raise HydroPannesInvalidResponseError("Lookup did not return a list")

        locations: dict[str, Location] = {}
        for item in body:
            if not isinstance(item, dict) or item.get("eligible") is False:
                continue
            location_id = item.get("lieuConsommation")
            if isinstance(location_id, str) and _LOCATION_ID_RE.match(location_id):
                locations.setdefault(location_id, Location.from_dict(item))
        return list(locations.values())

    async def close(self) -> None:
        """Close the session if the client opened it."""
        if self._session and self._close_session:
            await self._session.close()

    async def __aenter__(self) -> Self:
        """Enter the async context."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the session on exit."""
        await self.close()
