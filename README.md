# Async Python Load Balancer

An asynchronous HTTP reverse-proxy load balancer written in Python with `aiohttp`.

## Features

- Round-robin, least-connections, and random balancing strategies
- Active backend health checks
- Passive failure detection
- Automatic failover on connection/timeout errors
- Configurable retries for idempotent requests on 502/503/504
- Request body, query-string, and header forwarding
- `X-Forwarded-For`, `X-Forwarded-Proto`, and `X-Forwarded-Host` headers
- Hop-by-hop header stripping, including headers named dynamically in the `Connection` header
- Request timeout and maximum request body size limits
- Read-only status endpoint at `/_lb/status`
- Graceful aiohttp shutdown
- Docker and Docker Compose demo
- Unit and integration test suite (11 tests)

## Scope

A complete reverse-proxy and load-balancer implementation for learning, portfolio work, and controlled deployments. Not a drop-in replacement for mature edge proxies like HAProxy, Envoy, or NGINX. Doesn't implement TLS termination, HTTP/2 termination, WebSocket tunneling, dynamic service discovery, or distributed configuration.

## Requirements

Python 3.11+

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

## Quick start

Copy the example config:

```bash
cp config.example.json config.json
```

Start three demo backends in separate terminals:

```bash
BACKEND_NAME=backend-1 PORT=9001 python examples/backend_server.py
BACKEND_NAME=backend-2 PORT=9002 python examples/backend_server.py
BACKEND_NAME=backend-3 PORT=9003 python examples/backend_server.py
```

On Windows PowerShell:

```powershell
$env:BACKEND_NAME="backend-1"; $env:PORT="9001"; python examples/backend_server.py
```

Start the load balancer:

```bash
python -m load_balancer --config config.json
```

Then hit:

```
http://localhost:8080/hello
http://localhost:8080/_lb/status
```

Repeated requests to `/hello` rotate across healthy backends under `round_robin`.

## Configuration

```json
{
  "listen_host": "0.0.0.0",
  "listen_port": 8080,
  "strategy": "round_robin",
  "backends": [
    "http://127.0.0.1:9001",
    "http://127.0.0.1:9002"
  ],
  "request_timeout_seconds": 10.0,
  "retries": 1,
  "retry_statuses": [502, 503, 504],
  "health_check_interval_seconds": 5.0,
  "health_check_path": "/health",
  "health_check_timeout_seconds": 2.0,
  "health_failure_threshold": 2,
  "health_success_threshold": 1,
  "passive_failure_threshold": 2,
  "admin_status_enabled": true,
  "admin_status_path": "/_lb/status",
  "max_request_body_bytes": 10485760
}
```

Strategies: `round_robin`, `least_connections`, `random`.

Set `health_check_interval_seconds` to `0` to disable active health checks.

## Retry behavior

Transport failures (connection errors, timeouts) retry another healthy backend up to `retries` times.

HTTP retry statuses only retry for idempotent methods (`GET`, `HEAD`, `OPTIONS`, `PUT`, `DELETE`, `TRACE`), so a non-idempotent `POST` never gets silently duplicated.

## Tests

```bash
pytest
```

Covers balancing strategy behavior, header forwarding, retries, failover, health-state transitions, config validation, and the status endpoint.

## Docker Compose demo

```bash
docker compose up --build
```

Then send requests to `http://localhost:8080/anything`.

## Architecture

```
Client
  |
  v
Load Balancer
  strategy + backend pool
  retries + health checks
  |
  +-------+-------+
  |       |       |
  v       v       v
Backend Backend Backend
 :9001   :9002   :9003
```

## Project layout

```
load_balancer/
  app.py          reverse proxy and app lifecycle
  backend.py      backend state and statistics
  config.py       validated JSON configuration
  health.py       active health checking
  strategies.py   balancing algorithms
  __main__.py     command-line entry point
examples/
  backend_server.py
tests/
Dockerfile
docker-compose.yml
config.example.json
pyproject.toml
```
