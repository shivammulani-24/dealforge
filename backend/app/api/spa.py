"""B11 / D4-07: serve the built frontend from the same origin, with an SPA fallback.

* ``/assets/*`` is served from ``dist/assets``; a missing asset is a 404, never ``index.html``
  (otherwise HTML would be served where JavaScript was expected).
* Any other GET/HEAD path that isn't a real file gets ``index.html`` (client-side routing),
  with ``Cache-Control: no-cache`` and a strict Content-Security-Policy.
* **Never intercepted:** ``/api/…`` (unknown API paths keep the JSON 404 envelope for every
  method), ``/docs``, ``/redoc`` and ``/openapi.json``.
* Registered last, after every API router (``create_app`` guarantees the order; tested).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.services.errors import NotFound, ServiceError

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)
RESERVED = ("api", "docs", "redoc", "openapi.json")
ALL_METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


class MethodNotAllowed(ServiceError):
    status = 405
    code = "METHOD_NOT_ALLOWED"


def install_spa(app: FastAPI, dist: str) -> None:
    root = Path(dist).resolve()
    index = root / "index.html"
    if not index.is_file():
        return  # nothing built: the API runs exactly as without a frontend
    if (root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.api_route("/{full_path:path}", methods=ALL_METHODS, include_in_schema=False)
    async def spa(full_path: str, request: Request) -> Response:
        first = full_path.split("/", 1)[0]
        if first in RESERVED:
            raise NotFound(f"No API route matches /{full_path}.")
        if request.method not in ("GET", "HEAD"):
            raise MethodNotAllowed(f"{request.method} is not allowed on /{full_path}.")
        candidate = (root / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(
            index,
            headers={"Cache-Control": "no-cache", "Content-Security-Policy": CSP},
        )
