from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer


@pytest_asyncio.fixture
async def backend_factory() -> AsyncIterator[Callable[..., object]]:
    servers: list[TestServer] = []

    async def create(name: str, handler=None) -> str:
        app = web.Application()

        async def health(_: web.Request) -> web.Response:
            return web.json_response({"ok": True, "backend": name})

        async def default_handler(request: web.Request) -> web.Response:
            return web.json_response(
                {
                    "backend": name,
                    "method": request.method,
                    "path": request.path_qs,
                    "body": await request.text(),
                    "xff": request.headers.get("X-Forwarded-For"),
                    "xfh": request.headers.get("X-Forwarded-Host"),
                }
            )

        app.router.add_get("/health", health)
        app.router.add_route("*", "/{tail:.*}", handler or default_handler)
        server = TestServer(app)
        await server.start_server()
        servers.append(server)
        return str(server.make_url("")).rstrip("/")

    yield create

    for server in servers:
        await server.close()
