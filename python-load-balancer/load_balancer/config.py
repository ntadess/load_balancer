from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


@dataclass(slots=True)
class LoadBalancerConfig:
    backends: list[str]
    listen_host: str = "0.0.0.0"
    listen_port: int = 8080
    strategy: str = "round_robin"
    request_timeout_seconds: float = 10.0
    retries: int = 1
    retry_statuses: list[int] = field(default_factory=lambda: [502, 503, 504])
    health_check_interval_seconds: float = 5.0
    health_check_path: str = "/health"
    health_check_timeout_seconds: float = 2.0
    health_failure_threshold: int = 2
    health_success_threshold: int = 1
    passive_failure_threshold: int = 2
    admin_status_enabled: bool = True
    admin_status_path: str = "/_lb/status"
    max_request_body_bytes: int = 10 * 1024 * 1024

    def __post_init__(self) -> None:
        if not self.backends:
            raise ValueError("Configuration must contain at least one backend")
        if not 1 <= self.listen_port <= 65535:
            raise ValueError("listen_port must be between 1 and 65535")
        if self.retries < 0:
            raise ValueError("retries cannot be negative")
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be > 0")
        if self.health_check_interval_seconds < 0:
            raise ValueError("health_check_interval_seconds cannot be negative")
        if self.health_failure_threshold < 1 or self.health_success_threshold < 1:
            raise ValueError("health thresholds must be >= 1")
        if self.passive_failure_threshold < 0:
            raise ValueError("passive_failure_threshold cannot be negative")
        if self.max_request_body_bytes < 1:
            raise ValueError("max_request_body_bytes must be >= 1")
        if not self.health_check_path.startswith("/"):
            raise ValueError("health_check_path must start with /")
        if not self.admin_status_path.startswith("/"):
            raise ValueError("admin_status_path must start with /")

        normalized: list[str] = []
        for backend in self.backends:
            parsed = urlparse(backend)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"Invalid backend URL: {backend!r}")
            if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
                raise ValueError(
                    f"Backend URL must be only scheme + host + optional port, got: {backend!r}"
                )
            normalized.append(backend.rstrip("/"))
        self.backends = normalized

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "LoadBalancerConfig":
        return cls(**data)  # type: ignore[arg-type]

    @classmethod
    def from_json_file(cls, path: str | Path) -> "LoadBalancerConfig":
        with Path(path).open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("Configuration JSON must contain an object at the top level")
        return cls.from_dict(data)
