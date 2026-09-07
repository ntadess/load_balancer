from __future__ import annotations

import pytest
from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer

from load_balancer.backend import Backend
from load_balancer.config import LoadBalancerConfig
from load_balancer.health import HealthChecker
from load_balancer.strategies import BackendPool, RoundRobinStrategy


@pytest.mark.asyncio
async def test_health_checker_marks_backend_down_and_recovers() -> None:
    state = {"healthy": False}

    async def health(_: web.Request) -> web.Response:
        return web.Response(status=200 if state["healthy"] else 500)

    app = web.Application()
    app.router.add_get("/health", health)
    server = TestServer(app)
    await server.start_server()
    backend = Backend(str(server.make_url("")).rstrip("/"))
    config = LoadBalancerConfig(
        backends=[backend.url],
        health_check_interval_seconds=0,
        health_failure_threshold=1,
        health_success_threshold=1,
    )
    pool = BackendPool([backend], RoundRobinStrategy())

    try:
        async with ClientSession() as session:
            checker = HealthChecker(pool, session, config)
            await checker.check_once()
            assert backend.healthy is False
            state["healthy"] = True
            await checker.check_once()
            assert backend.healthy is True
    finally:
        await server.close()
