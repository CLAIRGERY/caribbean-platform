"""Structured API errors — one envelope for every failure.

    {"error": {"code": "DATABASE_UNAVAILABLE", "message": "...", "details": {...}}}

Codes are stable and documented; the frontend can branch on them without
parsing prose.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class ApiError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message: str = "unexpected error", *, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def envelope(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return {"error": payload}


class InvalidParameter(ApiError):
    status_code = 400
    code = "INVALID_PARAMETER"


class DatabaseUnavailable(ApiError):
    status_code = 503
    code = "DATABASE_UNAVAILABLE"


class DatabaseNotConfigured(ApiError):
    status_code = 503
    code = "DATABASE_NOT_CONFIGURED"


class UpstreamUnavailable(ApiError):
    status_code = 503
    code = "UPSTREAM_UNAVAILABLE"


class NotFound(ApiError):
    status_code = 404
    code = "NOT_FOUND"


class PayloadTooLarge(ApiError):
    status_code = 413
    code = "PAYLOAD_TOO_LARGE"


def classify_db_error(exc: BaseException) -> ApiError:
    """Never leak DSNs, credentials or SQL into the HTTP response."""
    text = str(exc).lower()
    if "statement timeout" in text or "canceling statement" in text:
        return DatabaseUnavailable("database query timed out", details={"reason": "statement_timeout"})
    if "too many connections" in text:
        return DatabaseUnavailable("database connection pool exhausted", details={"reason": "pool_exhausted"})
    if "does not exist" in text and "relation" in text:
        return DatabaseUnavailable("schema not initialised", details={"reason": "missing_relation"})
    return DatabaseUnavailable("database unavailable", details={"reason": type(exc).__name__})
