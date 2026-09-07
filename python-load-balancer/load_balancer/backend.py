from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic


@dataclass(slots=True)
class Backend:
    url: str
    healthy: bool = True
    current_connections: int = 0
    consecutive_health_failures: int = 0
    consecutive_health_successes: int = 0
    passive_failures: int = 0
    total_requests: int = 0
    total_failures: int = 0
    last_health_check: float | None = None
    last_error: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.url = self.url.rstrip("/")

    def begin_request(self) -> None:
        self.current_connections += 1
        self.total_requests += 1

    def end_request(self) -> None:
        self.current_connections = max(0, self.current_connections - 1)

    def record_passive_success(self) -> None:
        self.passive_failures = 0

    def record_passive_failure(self, error: str, threshold: int) -> None:
        self.passive_failures += 1
        self.total_failures += 1
        self.last_error = error
        if threshold > 0 and self.passive_failures >= threshold:
            self.healthy = False

    def record_health_result(
        self,
        ok: bool,
        *,
        failure_threshold: int,
        success_threshold: int,
        error: str | None = None,
    ) -> None:
        self.last_health_check = monotonic()
        if ok:
            self.consecutive_health_successes += 1
            self.consecutive_health_failures = 0
            self.last_error = None
            self.passive_failures = 0
            if self.consecutive_health_successes >= success_threshold:
                self.healthy = True
        else:
            self.consecutive_health_failures += 1
            self.consecutive_health_successes = 0
            self.last_error = error
            if self.consecutive_health_failures >= failure_threshold:
                self.healthy = False

    def as_dict(self) -> dict[str, object]:
        return {
            "url": self.url,
            "healthy": self.healthy,
            "current_connections": self.current_connections,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "passive_failures": self.passive_failures,
            "last_error": self.last_error,
        }
