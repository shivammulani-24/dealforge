"""One error envelope for every failure; ``error_type`` says which layer refused the request.

* ``validation``      the request was malformed (Pydantic); the engine never ran
* ``calculation``     well-formed but financially invalid or missing (engine ``EngineError``)
* ``not_found`` / ``conflict`` / ``import`` / ``authentication`` / ``immutable``
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.db.models import ImmutableRunError
from app.engine.errors import EngineError
from app.engine.version import ENGINE_VERSION
from app.services.errors import Conflict, ImportRejected, NotFound, ServiceError, Unauthorized

ERROR_TYPES: dict[type[ServiceError], str] = {
    NotFound: "not_found",
    Conflict: "conflict",
    ImportRejected: "import",
    Unauthorized: "authentication",
}


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_clean(v) for v in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def install(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e["loc"]), "code": e["type"], "message": e["msg"]} for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422, content={"error_type": "validation", "status": 422, "errors": errors}
        )

    @app.exception_handler(EngineError)
    async def _engine(_: Request, exc: EngineError) -> JSONResponse:
        errors = [
            {"field": i.field, "code": i.code, "severity": i.severity.value, "message": i.message}
            for i in exc.issues
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error_type": "calculation",
                "status": 422,
                "errors": errors,
                "engine_version": ENGINE_VERSION,
            },
        )

    @app.exception_handler(ServiceError)
    async def _service(_: Request, exc: ServiceError) -> JSONResponse:
        etype = next((t for cls, t in ERROR_TYPES.items() if isinstance(exc, cls)), "validation")
        headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, Unauthorized) else None
        return JSONResponse(
            status_code=exc.status,
            headers=headers,
            content={
                "error_type": etype,
                "status": exc.status,
                "errors": [
                    {"code": exc.code, "message": exc.message, "detail": _clean(exc.detail)}
                ],
            },
        )

    @app.exception_handler(ImmutableRunError)
    async def _immutable(_: Request, exc: ImmutableRunError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "error_type": "immutable",
                "status": 409,
                "errors": [{"code": "RUN_IMMUTABLE", "message": str(exc)}],
            },
        )
