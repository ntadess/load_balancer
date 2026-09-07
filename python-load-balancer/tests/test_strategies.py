from load_balancer.backend import Backend
from load_balancer.strategies import LeastConnectionsStrategy, RoundRobinStrategy


def test_round_robin_cycles() -> None:
    backends = [Backend("http://a:1"), Backend("http://b:2"), Backend("http://c:3")]
    strategy = RoundRobinStrategy()
    assert [strategy.choose(backends).url for _ in range(5)] == [
        "http://a:1",
        "http://b:2",
        "http://c:3",
        "http://a:1",
        "http://b:2",
    ]


def test_least_connections_prefers_least_busy() -> None:
    a = Backend("http://a:1", current_connections=3)
    b = Backend("http://b:2", current_connections=1)
    c = Backend("http://c:3", current_connections=2)
    assert LeastConnectionsStrategy().choose([a, b, c]) is b
