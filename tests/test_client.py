"""Tests of the HTTP client, against a local aiohttp server."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from pyhydropannes import (
    HydroPannesAmbiguousAddressError,
    HydroPannesClient,
    HydroPannesConnectionError,
    HydroPannesInvalidLocationIdError,
    HydroPannesInvalidPostalCodeError,
    HydroPannesInvalidResponseError,
    HydroPannesLocationNotFoundError,
    HydroPannesServerError,
    HydroPannesStatusError,
    HydroPannesTimeoutError,
    normalize_postal_code,
)
from pyhydropannes import client as client_module

from .helpers import make_payload

LIEU = "0000001234"

# A queued answer: a Response, or a callable raising or stalling.
Answer = web.StreamResponse | Callable[[], Any]


@dataclass
class FakeApi:
    """Serves queued answers and records the query of each request."""

    answers: list[Answer] = field(default_factory=list)
    queries: list[dict[str, str]] = field(default_factory=list)

    async def handle(self, request: web.Request) -> web.StreamResponse:
        self.queries.append(dict(request.query))
        answer = self.answers.pop(0)
        if isinstance(answer, web.StreamResponse):
            return answer
        result = answer()
        if asyncio.iscoroutine(result):
            result = await result
        assert isinstance(result, web.StreamResponse)
        return result


@pytest.fixture
async def api(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[FakeApi]:
    fake = FakeApi()
    app = web.Application()
    app.router.add_get("/etats/{lieu}", fake.handle)
    app.router.add_get("/locations", fake.handle)
    server = TestServer(app)
    await server.start_server()
    base = str(server.make_url(""))
    monkeypatch.setattr(client_module, "API_URL", base + "/etats/{}")
    monkeypatch.setattr(client_module, "SEARCH_URL", base + "/locations")
    yield fake
    await server.close()


@pytest.fixture
async def client() -> AsyncIterator[HydroPannesClient]:
    async with aiohttp.ClientSession() as session:
        yield HydroPannesClient(session, request_timeout=0.5, retry_delay=0)


def _json(body: Any, status: int = 200) -> web.Response:
    return web.json_response(body, status=status)


async def _stall() -> web.Response:
    await asyncio.sleep(2)
    return _json([])  # pragma: no cover


def _lieu(numero: str, **extra: Any) -> dict[str, Any]:
    return {
        "lieuConsommation": numero,
        "adresseCompleteFr": "1, rue Exemple, Qc A1A&nbsp;1A1",
        **extra,
    }


async def test_get_etat_returns_first_object(api: FakeApi, client: HydroPannesClient) -> None:
    payload = make_payload()
    api.answers.append(_json([payload]))
    assert await client.async_get_payload(f" {LIEU} ") == payload


@pytest.mark.parametrize("lieu", ["123", "abcdefghij", "12345678901"])
async def test_get_etat_rejects_bad_number(client: HydroPannesClient, lieu: str) -> None:
    with pytest.raises(HydroPannesInvalidLocationIdError):
        await client.async_get_payload(lieu)


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ([], HydroPannesLocationNotFoundError),
        ({"etat": "A"}, HydroPannesInvalidResponseError),
        (["x"], HydroPannesInvalidResponseError),
    ],
)
async def test_get_etat_bad_bodies(
    api: FakeApi, client: HydroPannesClient, body: Any, error: type[Exception]
) -> None:
    api.answers.append(_json(body))
    with pytest.raises(error):
        await client.async_get_payload(LIEU)


async def test_get_etat_not_json(api: FakeApi, client: HydroPannesClient) -> None:
    api.answers.append(web.Response(text="<html>"))
    with pytest.raises(HydroPannesInvalidResponseError):
        await client.async_get_payload(LIEU)


async def test_get_etat_4xx_not_retried(api: FakeApi, client: HydroPannesClient) -> None:
    api.answers.append(web.Response(status=404))
    with pytest.raises(HydroPannesStatusError) as err:
        await client.async_get_payload(LIEU)
    assert err.value.status == 404
    assert len(api.queries) == 1


async def test_get_etat_retries_then_succeeds(api: FakeApi, client: HydroPannesClient) -> None:
    payload = make_payload()
    api.answers += [web.Response(status=503), _stall, _json([payload])]
    assert await client.async_get_payload(LIEU) == payload
    assert len(api.queries) == 3


@pytest.mark.parametrize(
    ("answer", "error"),
    [(lambda: web.Response(status=502), HydroPannesServerError), (_stall, HydroPannesTimeoutError)],
)
async def test_get_etat_gives_up(
    api: FakeApi, client: HydroPannesClient, answer: Answer, error: type[Exception]
) -> None:
    api.answers += [answer] * 3
    with pytest.raises(error) as err:
        await client.async_get_payload(LIEU)
    assert isinstance(err.value, HydroPannesConnectionError)
    assert err.value.attempts == 3


async def test_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # Nothing listens on port 1.
    monkeypatch.setattr(client_module, "API_URL", "http://127.0.0.1:1/{}")
    async with HydroPannesClient(max_retries=0) as client:
        with pytest.raises(HydroPannesConnectionError) as err:
            await client.async_get_payload(LIEU)
    assert type(err.value) is HydroPannesConnectionError
    assert isinstance(err.value.__cause__, aiohttp.ClientError)


async def test_own_session_is_closed(api: FakeApi) -> None:
    api.answers.append(web.Response(status=500))
    client = HydroPannesClient(max_retries=0)
    with pytest.raises(HydroPannesServerError) as err:
        await client.async_get_payload(LIEU)
    assert (err.value.status, err.value.attempts) == (500, 1)
    session = client._session
    assert session is not None
    await client.close()
    assert session.closed


async def test_given_session_is_left_open() -> None:
    async with aiohttp.ClientSession() as session:
        await HydroPannesClient(session).close()
        assert not session.closed


async def test_search_dedups_and_filters(api: FakeApi, client: HydroPannesClient) -> None:
    api.answers.append(
        _json(
            [
                _lieu("0000000001"),
                _lieu("0000000001"),
                _lieu("0000000002", eligible=False),
                {"lieuConsommation": "abc"},
                "x",
            ]
        )
    )
    locations = await client.async_search_locations("a1a1a1", " 12 ", " 3 ")
    assert [location.id for location in locations] == ["0000000001"]
    assert locations[0].full_address == "1, rue Exemple, Qc A1A 1A1"
    assert api.queries == [
        {"codePostal": "A1A 1A1", "numeroAppartement": "3", "numeroCivique": "12", "nomRue": ""}
    ]


async def test_search_ambiguous(api: FakeApi, client: HydroPannesClient) -> None:
    api.answers.append(_json({"error": {"code": "BSSP0001"}}, status=400))
    with pytest.raises(HydroPannesAmbiguousAddressError):
        await client.async_search_locations("A1A 1A1", "12")


@pytest.mark.parametrize(
    ("answer", "error"),
    [
        (_json({"error": {"code": "OTHER"}}, status=400), HydroPannesStatusError),
        (web.Response(status=400, text="nope"), HydroPannesStatusError),
        (web.Response(status=404), HydroPannesStatusError),
        (_json({"not": "a list"}), HydroPannesInvalidResponseError),
    ],
)
async def test_search_errors(
    api: FakeApi, client: HydroPannesClient, answer: web.Response, error: type[Exception]
) -> None:
    api.answers.append(answer)
    with pytest.raises(error):
        await client.async_search_locations("A1A 1A1", "12")


@pytest.mark.parametrize("code", ["12345", "AAA111", ""])
def test_normalize_postal_code_rejects(code: str) -> None:
    with pytest.raises(HydroPannesInvalidPostalCodeError):
        normalize_postal_code(code)
