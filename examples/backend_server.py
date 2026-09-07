from __future__ import annotations

import os
from aiohttp import web

NAME = os.environ.get("BACKEND_NAME", "backend")
PORT = int(os.environ.get("PORT", "9001"))


async def health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "backend": NAME})


async def handle(request: web.Request) -> web.Response:
    body = await request.text()
    return web.json_response(
        {
            "backend": NAME,
            "method": request.method,
            "path": request.path_qs,
            "body": body,
            "x_forwarded_for": request.headers.get("X-Forwarded-For"),
            "x_forwarded_proto": request.headers.get("X-Forwarded-Proto"),
            "x_forwarded_host": request.headers.get("X-Forwarded-Host"),
        }
    )


app = web.Application()
app.router.add_get("/health", health)
app.router.add_route("*", "/{tail:.*}", handle)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
