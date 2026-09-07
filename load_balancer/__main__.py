from __future__ import annotations

import argparse
import logging
import os

from aiohttp import web

from .app import create_app
from .config import LoadBalancerConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Asynchronous Python HTTP load balancer")
    parser.add_argument(
        "--config",
        default=os.environ.get("LOAD_BALANCER_CONFIG", "config.json"),
        help="Path to JSON configuration file (default: config.json)",
    )
    parser.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = LoadBalancerConfig.from_json_file(args.config)
    web.run_app(create_app(config), host=config.listen_host, port=config.listen_port)


if __name__ == "__main__":
    main()
