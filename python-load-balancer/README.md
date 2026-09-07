# Async Python Load Balancer

A GitHub-ready asynchronous HTTP reverse-proxy load balancer written in Python with `aiohttp`.

## Features

- Round-robin, least-connections, and random balancing
- Active backend health checks
- Passive failure detection
- Automatic failover on connection/timeout errors
- Configurable retries for idempotent requests on 502/503/504
- Request body, query-string, and header forwarding
- `X-Forwarded-For`, `X-Forwarded-Proto`, and `X-Forwarded-Host`
- Hop-by-hop header stripping
- Request timeout and maximum request body configuration
- Read-only status endpoint at `/_lb/status`
- Graceful aiohttp cleanup
- Docker and Docker Compose demo
- Unit and integration test suite

## Scope

This project is a complete HTTP reverse-proxy/load-balancer implementation for learning, portfolio work, and controlled deployments. It is not a drop-in replacement for mature edge proxies such as HAProxy, Envoy, or NGINX. It does not currently implement TLS termination, HTTP/2 termination, WebSocket tunneling, dynamic service discovery, or distributed configuration.

## Requirements

- Python 3.11+

## Install

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -e ".[dev]"
```

## Quick start

Copy the example config:

```bash
# Windows
copy config.example.json config.json

# macOS/Linux
cp config.example.json config.json
```

Start three demo backends in separate terminals:

```bash
# terminal 1
set BACKEND_NAME=backend-1 && set PORT=9001 && python examples/backend_server.py

# terminal 2
set BACKEND_NAME=backend-2 && set PORT=9002 && python examples/backend_server.py

# terminal 3
set BACKEND_NAME=backend-3 && set PORT=9003 && python examples/backend_server.py
```

On PowerShell use:

```powershell
$env:BACKEND_NAME="backend-1"; $env:PORT="9001"; python examples/backend_server.py
```

Then start the load balancer:

```bash
python -m load_balancer --config config.json
```

Visit:

```text
http://localhost:8080/hello
http://localhost:8080/_lb/status
```

Repeated `/hello` requests will rotate across healthy backends when using `round_robin`.

## Configuration

Example:

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

Supported strategies:

- `round_robin`
- `least_connections`
- `random`

Set `health_check_interval_seconds` to `0` to disable active health checks.

## Retry behavior

Transport failures such as connection errors and timeouts can retry another healthy backend up to `retries` times.

HTTP retry statuses are retried only for idempotent methods (`GET`, `HEAD`, `OPTIONS`, `PUT`, `DELETE`, `TRACE`) so the proxy does not accidentally duplicate a non-idempotent `POST` operation.

## Run tests

```bash
pytest
```

The tests cover balancing strategy behavior, forwarding, retries, failover, health-state transitions, config validation, and the status endpoint.

## Docker Compose demo

```bash
docker compose up --build
```

Then send requests to:

```text
http://localhost:8080/anything
```

## Push to GitHub

```bash
git init
git add .
git commit -m "Build asynchronous Python load balancer"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/python-load-balancer.git
git push -u origin main
```

## Architecture

```text
Client
  |
  v
+---------------------------+
| Python Load Balancer      |
|                           |
| strategy + backend pool   |
| retries + health checks   |
+------------+--------------+
             |
     +-------+-------+
     |       |       |
     v       v       v
 Backend  Backend  Backend
   :9001   :9002   :9003
```

## Project layout

```text
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
