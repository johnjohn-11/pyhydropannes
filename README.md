# pyhydropannes

Async Python client for Hydro-Québec's public Info-pannes outage service, used by the Hydro-Pannes Home Assistant integration.

It fetches the outage state of a consumption location, looks up the locations at an address and reads a payload the way the Info-pannes site does.

## Usage

```python
import asyncio

import aiohttp

from pyhydropannes import HydroPannesClient


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        client = HydroPannesClient(session)
        locations = await client.async_search_locations("A1A 1A1", "123")
        state = await client.async_get_state(locations[0].id)
        print(state.service_status, state.intervention_step, state.restoration_step)
        if state.current:
            print(state.current.cause, state.current.display_end)


asyncio.run(main())
```

`service_status`, `intervention_step` and `restoration_step` are what the Info-pannes site shows for the location, as enumerations. `async_get_payload()` returns the raw payload instead, to be read with `LocationState.from_payload()`.

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
