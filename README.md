# pyhydropannes

Async Python client for Hydro-Québec's public Info-pannes outage service, used by the Hydro-Pannes Home Assistant integration.

It fetches the outage state of a consumption location, looks up the locations at an address and reads a payload the way the Info-pannes site does.

## Usage

```python
import asyncio

import aiohttp

from pyhydropannes import HydroPannesClient, LocationState


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        client = HydroPannesClient(session)
        locations = await client.async_search_locations("A1A 1A1", "123")
        payload = await client.async_get_payload(locations[0].id)
        state = LocationState.from_payload(payload)
        print(state.active_outage, state.planned)


asyncio.run(main())
```

5xx answers, timeouts and connection errors are retried (`max_retries`, `retry_delay`). Every error raised derives from `HydroPannesError`.

## Development

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/ruff check src tests
.venv/bin/mypy
.venv/bin/pytest --cov=pyhydropannes
```

## Disclaimer

This project is not affiliated with Hydro-Québec. The endpoints it uses are the ones the public Info-pannes site calls and are not documented by Hydro-Québec.
