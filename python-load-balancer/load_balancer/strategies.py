from __future__ import annotations

import random
from abc import ABC, abstractmethod

from .backend import Backend


class BalancingStrategy(ABC):
    @abstractmethod
    def choose(self, backends: list[Backend]) -> Backend | None:
        raise NotImplementedError


class RoundRobinStrategy(BalancingStrategy):
    def __init__(self) -> None:
        self._cursor = 0

    def choose(self, backends: list[Backend]) -> Backend | None:
        if not backends:
            return None
        backend = backends[self._cursor % len(backends)]
        self._cursor = (self._cursor + 1) % max(1, len(backends))
        return backend


class LeastConnectionsStrategy(BalancingStrategy):
    def choose(self, backends: list[Backend]) -> Backend | None:
        if not backends:
            return None
        return min(backends, key=lambda b: (b.current_connections, b.total_requests, b.url))


class RandomStrategy(BalancingStrategy):
    def choose(self, backends: list[Backend]) -> Backend | None:
        return random.choice(backends) if backends else None


def make_strategy(name: str) -> BalancingStrategy:
    normalized = name.strip().lower().replace("-", "_")
    strategies: dict[str, type[BalancingStrategy]] = {
        "round_robin": RoundRobinStrategy,
        "least_connections": LeastConnectionsStrategy,
        "random": RandomStrategy,
    }
    try:
        return strategies[normalized]()
    except KeyError as exc:
        allowed = ", ".join(sorted(strategies))
        raise ValueError(f"Unknown balancing strategy {name!r}. Choose one of: {allowed}") from exc


class BackendPool:
    def __init__(self, backends: list[Backend], strategy: BalancingStrategy) -> None:
        if not backends:
            raise ValueError("At least one backend is required")
        self.backends = backends
        self.strategy = strategy

    def choose(self, *, exclude: set[str] | None = None) -> Backend | None:
        excluded = exclude or set()
        healthy = [b for b in self.backends if b.healthy and b.url not in excluded]
        return self.strategy.choose(healthy)

    def snapshot(self) -> list[dict[str, object]]:
        return [backend.as_dict() for backend in self.backends]
