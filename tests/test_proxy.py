from __future__ import annotations

import socket

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from load_balancer.app import create_app
from load_balancer.config import LoadBalancerConfig


async def make_client(config: LoadBalancerConfig) -> TestClient:
    server = TestServer(create_app(config))
    client = TestClient(server)
    await client.start_server()
    return client


@pytest.mark.asyncio
async def test_round_robin_proxy(backend_factory) -> None:
    a = await backend_factory("a")
    b = await backend_factory("b")
    client = await make_client(
        LoadBalancerConfig(backends=[a, b], health_check_interval_seconds=0, retries=0)
    )
    try:
        seen = []
        for i in range(4):
            response = await client.get(f"/hello?i={i}")
            assert response.status == 200
            payload = await response.json()
            seen.append(payload["backend"])
            assert payload["path"] == f"/hello?i={i}"
        assert seen == ["a", "b", "a", "b"]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_forwards_body_and_forwarded_headers(backend_factory) -> None:
    backend = await backend_factory("echo")
    client = await make_client(
        LoadBalancerConfig(backends=[backend], health_check_interval_seconds=0, retries=0)
    )
    try:
        response = await client.post(
            "/submit?x=1",
            data="payload",
            headers={"Host": "public.example.com"},
        )
        payload = await response.json()
        assert payload["backend"] == "echo"
        assert payload["method"] == "POST"
        assert payload["body"] == "payload"
        assert payload["xfh"] == "public.example.com"
        assert payload["xff"]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_transport_failure_retries_next_backend(backend_factory) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        dead_port = sock.getsockname()[1]
    dead = f"http://127.0.0.1:{dead_port}"
    good = await backend_factory("good")

    client = await make_client(
        LoadBalancerConfig(
            backends=[dead, good],
            health_check_interval_seconds=0,
            retries=1,
            passive_failure_threshold=1,
        )
    )
    try:
        response = await client.get("/retry-me")
        assert response.status == 200
        assert (await response.json())["backend"] == "good"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_retryable_503_retries_for_get(backend_factory) -> None:
    async def unavailable(_: web.Request) -> web.Response:
        return web.Response(status=503, text="busy")

    bad = await backend_factory("bad", handler=unavailable)
    good = await backend_factory("good")
    client = await make_client(
        LoadBalancerConfig(
            backends=[bad, good],
            health_check_interval_seconds=0,
            retries=1,
            retry_statuses=[503],
        )
    )
    try:
        response = await client.get("/resource")
        assert response.status == 200
        assert (await response.json())["backend"] == "good"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_post_is_not_retried_on_503(backend_factory) -> None:
    calls = {"bad": 0, "good": 0}

    async def unavailable(_: web.Request) -> web.Response:
        calls["bad"] += 1
        return web.Response(status=503, text="busy")

    async def should_not_run(_: web.Request) -> web.Response:
        calls["good"] += 1
        return web.Response(status=200, text="ok")

    bad = await backend_factory("bad", handler=unavailable)
    good = await backend_factory("good", handler=should_not_run)
    client = await make_client(
        LoadBalancerConfig(
            backends=[bad, good],
            health_check_interval_seconds=0,
            retries=1,
            retry_statuses=[503],
        )
    )
    try:
        response = await client.post("/unsafe", data="x")
        assert response.status == 503
        assert calls == {"bad": 1, "good": 0}
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_status_endpoint(backend_factory) -> None:
    backend = await backend_factory("a")
    client = await make_client(
        LoadBalancerConfig(backends=[backend], health_check_interval_seconds=0)
    )
    try:
        response = await client.get("/_lb/status")
        assert response.status == 200
        payload = await response.json()
        assert payload["total_backends"] == 1
        assert payload["healthy_backends"] == 1
        assert payload["backends"][0]["url"] == backend
    finally:
        await client.close()
