import pytest

from load_balancer.config import LoadBalancerConfig


def test_config_rejects_invalid_backend() -> None:
    with pytest.raises(ValueError):
        LoadBalancerConfig(backends=["not-a-url"])


def test_config_normalizes_backend_slash() -> None:
    config = LoadBalancerConfig(backends=["http://localhost:9001/"])
    assert config.backends == ["http://localhost:9001"]
