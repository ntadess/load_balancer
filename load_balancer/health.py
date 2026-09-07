from __future__ import annotations

import asyncio
import logging

import aiohttp

from .config import LoadBalancerConfig
from .strategies import BackendPool

logger = logging.getLogger(__name__)


class HealthChecker:
    def __init__(
        self,
        pool: BackendPool,
        session: aiohttp.ClientSession,
        config: LoadBalancerConfig,
    ) -> None:
        self.pool = pool
        self.session = session
        self.config = config
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if self.config.health_check_interval_seconds <= 0 or self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="load-balancer-health-checker")

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def check_once(self) -> None:
        await asyncio.gather(*(self._check_backend(backend) for backend in self.pool.backends))

    async def _run(self) -> None:
        try:
            while not self._stopping.is_set():
                await self.check_once()
                try:
                    await asyncio.wait_for(
                        self._stopping.wait(),
                        timeout=self.config.health_check_interval_seconds,
                    )
                except TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise

    async def _check_backend(self, backend) -> None:
        url = f"{backend.url}{self.config.health_check_path}"
        timeout = aiohttp.ClientTimeout(total=self.config.health_check_timeout_seconds)
        ok = False
        error: str | None = None
        try:
            async with self.session.get(url, timeout=timeout, allow_redirects=False) as response:
                await response.read()
                ok = 200 <= response.status < 400
                if not ok:
                    error = f"health check returned HTTP {response.status}"
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            error = f"{type(exc).__name__}: {exc}"

        was_healthy = backend.healthy
        backend.record_health_result(
            ok,
            failure_threshold=self.config.health_failure_threshold,
            success_threshold=self.config.health_success_threshold,
            error=error,
        )
        if was_healthy != backend.healthy:
            logger.warning("backend %s health changed to %s", backend.url, backend.healthy)
