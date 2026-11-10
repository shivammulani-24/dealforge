"""Test-only ASGI middleware: every successful response must validate against the model its route
documents (B6). A mismatch raises, failing the test that made the request."""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

VALIDATED: set[tuple[str, str]] = set()  # (method, route path) pairs validated so far


class ResponseSchemaError(AssertionError):
    pass


def _all_routes(routes: Any) -> list[Any]:
    """Flatten included routers. This FastAPI version wraps them (``_IncludedRouter``); the
    route seen at request time (``scope["route"]``) is the original, unprefixed APIRoute."""
    out: list[Any] = []
    for r in routes:
        inner = getattr(r, "original_router", None)
        out.extend(_all_routes(inner.routes) if inner is not None else [r])
    return out


def documented_routes(app: Any) -> set[tuple[str, str]]:
    out = set()
    for route in _all_routes(app.routes):
        responses = getattr(route, "responses", None) or {}
        if any(isinstance(v, dict) and "model" in v for v in responses.values()):
            for m in route.methods - {"HEAD"}:
                out.add((m, route.path))
    return out


class ResponseSchemaValidator:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        status: dict[str, int] = {}
        chunks: list[bytes] = []

        async def capture(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
            await send(message)

        await self.app(scope, receive, capture)
        route = scope.get("route")
        code = status.get("code", 0)
        responses = getattr(route, "responses", None) or {}
        spec = responses.get(code) or responses.get(str(code))
        if not (200 <= code < 300 and isinstance(spec, dict) and "model" in spec):
            return
        raw = b"".join(chunks) or b"null"
        try:
            # Strict JSON-mode validation: no coercion ("3" is not an int), while JSON-native
            # encodings (ISO dates, arrays for tuples, enum values) are accepted.
            TypeAdapter(spec["model"]).validate_json(raw, strict=True)
        except Exception as exc:  # pragma: no cover - only on drift
            raise ResponseSchemaError(
                f"{scope['method']} {route.path} → {code} does not match its documented "
                f"model:\n{exc}"
            ) from exc
        VALIDATED.add((scope["method"], route.path))
