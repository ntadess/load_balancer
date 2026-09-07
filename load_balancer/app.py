from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

import aiohttp
from aiohttp import web
from multidict import CIMultiDict

from .backend import Backend
from .config import LoadBalancerConfig
from .health import HealthChecker
from .strategies import BackendPool, make_strategy

logger = logging.getLogger(__name__)

POOL_KEY = web.AppKey("backend_pool", BackendPool)
SESSION_KEY = web.AppKey("client_session", aiohttp.ClientSession)
HEALTH_KEY = web.AppKey("health_checker", HealthChecker)
CONFIG_KEY = web.AppKey("config", LoadBalancerConfig)

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
IDEMPOTENT_METHODS = {"GET", "HEAD", "OPTIONS", "PUT", "DELETE", "TRACE"}


def _connection_tokens(headers: Iterable[tuple[str, str]]) -> set[str]:
    tokens: set[str] = set()
    for name, value in headers:
        if name.lower() == "connection":
            tokens.update(token.strip().lower() for token in value.split(",") if token.strip())
    return tokens


def _filter_headers(headers: Iterable[tuple[str, str]], *, remove_host: bool = False) -> CIMultiDict[str]:
    pairs = list(headers)
    dynamic_hop_headers = _connection_tokens(pairs)
    blocked = HOP_BY_HOP_HEADERS | dynamic_hop_headers | {"content-length"}
    if remove_host:
        blocked.add("host")

    filtered = CIMultiDict()
    for name, value in pairs:
        if name.lower() not in blocked:
            filtered.add(name, value)
    return filtered


def _upstream_headers(request: web.Request, backend: Backend) -> CIMultiDict[str]:
    headers = _filter_headers(request.headers.items(), remove_host=True)
    original_host = request.headers.get("Host", "")
    forwarded_for = request.headers.get("X-Forwarded-For")
    remote = request.remote or "unknown"
    headers["X-Forwarded-For"] = f"{forwarded_for}, {remote}" if forwarded_for else remote
    headers["X-Forwarded-Proto"] = request.scheme
    if original_host:
        headers["X-Forwarded-Host"] = original_host

    # aiohttp supplies the correct Host header for the backend URL when Host is omitted.
    return headers


async def _status_handler(request: web.Request) -> web.Response:
    pool = request.app[POOL_KEY]
    config = request.app[CONFIG_KEY]
    return web.json_response(
        {
            "strategy": config.strategy,
            "healthy_backends": sum(1 for b in pool.backends if b.healthy),
            "total_backends": len(pool.backends),
            "backends": pool.snapshot(),
        }
    )


async def _proxy_handler(request: web.Request) -> web.StreamResponse:
    app = request.app
    config = app[CONFIG_KEY]
    pool = app[POOL_KEY]
    session = app[SESSION_KEY]

    if config.admin_status_enabled and request.path == config.admin_status_path:
        return await _status_handler(request)

    body = await request.read()
    tried: set[str] = set()
    max_attempts = min(len(pool.backends), config.retries + 1)
    if max_attempts <= 0:
        max_attempts = 1

    last_error: str | None = None
    last_response: tuple[int, CIMultiDict[str], bytes] | None = None

    for attempt in range(max_attempts):
        backend = pool.choose(exclude=tried)
        if backend is None:
            break
        tried.add(backend.url)
        backend.begin_request()
        target_url = f"{backend.url}{request.raw_path}"
        headers = _upstream_headers(request, backend)
        timeout = aiohttp.ClientTimeout(total=config.request_timeout_seconds)

        try:
            async with session.request(
                request.method,
                target_url,
                headers=headers,
                data=body if body else None,
                timeout=timeout,
                allow_redirects=False,
            ) as upstream:
                response_body = await upstream.read()
                response_headers = _filter_headers(upstream.headers.items())
                last_response = (upstream.status, response_headers, response_body)

                should_retry_status = (
                    upstream.status in config.retry_statuses
                    and request.method.upper() in IDEMPOTENT_METHODS
                    and attempt + 1 < max_attempts
                )
                if should_retry_status:
                    backend.total_failures += 1
                    last_error = f"upstream returned retryable HTTP {upstream.status}"
                    logger.warning(
                        "retrying %s %s after %s returned %s",
                        request.method,
                        request.path_qs,
                        backend.url,
                        upstream.status,
                    )
                    continue

                backend.record_passive_success()
                return web.Response(
                    status=upstream.status,
                    headers=response_headers,
                    body=response_body,
                )
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            backend.record_passive_failure(last_error, config.passive_failure_threshold)
            logger.warning("backend %s request failed: %s", backend.url, last_error)
        finally:
            backend.end_request()

    if last_response is not None:
        status, response_headers, response_body = last_response
        return web.Response(status=status, headers=response_headers, body=response_body)

    return web.json_response(
        {
            "error": "no backend could serve the request",
            "detail": last_error or "no healthy backends available",
        },
        status=503,
    )


async def _client_session_context(app: web.Application):
    session = aiohttp.ClientSession(auto_decompress=False)
    app[SESSION_KEY] = session
    checker = HealthChecker(app[POOL_KEY], session, app[CONFIG_KEY])
    app[HEALTH_KEY] = checker
    await checker.start()
    try:
        yield
    finally:
        await checker.stop()
        await session.close()


def create_app(config: LoadBalancerConfig) -> web.Application:
    strategy = make_strategy(config.strategy)
    backends = [Backend(url=url) for url in config.backends]
    pool = BackendPool(backends, strategy)

    app = web.Application(client_max_size=config.max_request_body_bytes)
    app[CONFIG_KEY] = config
    app[POOL_KEY] = pool
    app.cleanup_ctx.append(_client_session_context)
    app.router.add_route("*", "/{tail:.*}", _proxy_handler)
    return app
