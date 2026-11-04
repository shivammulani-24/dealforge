"""Service-level exceptions, mapped to HTTP responses by the API layer."""

from __future__ import annotations

from typing import Any


class ServiceError(Exception):
    status = 400
    code = "SERVICE_ERROR"

    def __init__(self, message: str, *, detail: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class NotFound(ServiceError):
    status = 404
    code = "NOT_FOUND"


class Conflict(ServiceError):
    status = 409
    code = "CONFLICT"


class ImportRejected(ServiceError):
    status = 422
    code = "IMPORT_REJECTED"


class Unauthorized(ServiceError):
    status = 401
    code = "UNAUTHORIZED"
