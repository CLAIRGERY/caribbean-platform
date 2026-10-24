"""Structured failure classification for SaKgaZé ingestion.

Why this module exists
----------------------
Historically the ingestion runner swallowed every per-source exception, logged it
and exited with status 0. GitHub therefore reported "green" runs that had
ingested nothing, and — inversely — an empty satellite acquisition (a perfectly
legitimate scientific outcome) looked identical to a broken pipeline. Monitoring
became meaningless.

Rules encoded here:
  * an empty acquisition is ``NO_NEW_DATA`` and is NOT a failure;
  * an authentication / configuration problem is a failure that must never be
    retried in a loop;
  * a transient upstream problem is a failure that MAY be retried;
  * every failure carries a stable machine-readable class + a stable exit code
    so GitHub Actions and humans can act on it.

The exit codes are part of the contract with
``.github/workflows/sakgaze-ingestion.yml`` — do not renumber them.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional


class ErrorClass(str, Enum):
    """Machine-readable ingestion outcome / failure category."""

    SUCCESS = "SUCCESS"
    NO_NEW_DATA = "NO_NEW_DATA"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"

    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    INVALID_SCIENTIFIC_DATA = "INVALID_SCIENTIFIC_DATA"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


#: Outcome classes that mean "the pipeline did what it could" -> exit 0.
NON_FATAL = {
    ErrorClass.SUCCESS,
    ErrorClass.NO_NEW_DATA,
    ErrorClass.PARTIAL_SUCCESS,
}

#: Exit code per class. 0/10-19 = fatal (non-retryable), 20-29 = retryable,
#: 30+ = data/processing problems. Grouped so a shell script can branch on
#: ``code / 10`` if it ever needs to.
EXIT_CODES = {
    ErrorClass.SUCCESS: 0,
    ErrorClass.NO_NEW_DATA: 0,
    ErrorClass.PARTIAL_SUCCESS: 0,
    ErrorClass.AUTHENTICATION_ERROR: 10,
    ErrorClass.CONFIGURATION_ERROR: 11,
    ErrorClass.DATABASE_UNAVAILABLE: 12,
    ErrorClass.INVALID_SCIENTIFIC_DATA: 13,
    ErrorClass.UPSTREAM_UNAVAILABLE: 20,
    ErrorClass.NETWORK_TIMEOUT: 21,
    ErrorClass.RATE_LIMITED: 22,
    ErrorClass.PROCESSING_ERROR: 23,
    ErrorClass.UNKNOWN_ERROR: 29,
}

#: Classes worth retrying on the next scheduled run (nothing else is retried).
RETRYABLE = {
    ErrorClass.UPSTREAM_UNAVAILABLE,
    ErrorClass.NETWORK_TIMEOUT,
    ErrorClass.RATE_LIMITED,
    ErrorClass.PROCESSING_ERROR,
}


class IngestionError(Exception):
    """Ingestion failure carrying an explicit classification."""

    def __init__(self, error_class: ErrorClass, message: str, *, retryable: Optional[bool] = None):
        super().__init__(message)
        self.error_class = ErrorClass(error_class)
        self.message = message
        self.retryable = self.error_class in RETRYABLE if retryable is None else retryable

    def as_dict(self) -> dict:
        return {
            "error_class": self.error_class.value,
            "message": self.message,
            "retryable": self.retryable,
        }


class MissingCredentials(IngestionError):
    """A credential required for a collector is absent from the environment."""

    def __init__(self, variable: str, purpose: str):
        super().__init__(
            ErrorClass.CONFIGURATION_ERROR,
            f"missing credential {variable} ({purpose})",
            retryable=False,
        )
        self.variable = variable


def exit_code(error_class: ErrorClass) -> int:
    return EXIT_CODES.get(ErrorClass(error_class), EXIT_CODES[ErrorClass.UNKNOWN_ERROR])


def _name(exc: BaseException) -> str:
    return f"{type(exc).__module__}.{type(exc).__name__}".lower()


def _text(exc: BaseException) -> str:
    parts = [str(exc)]
    orig = getattr(exc, "orig", None)  # SQLAlchemy wraps driver exceptions here
    if orig is not None:
        parts.append(f"{type(orig).__module__}.{type(orig).__name__}: {orig}")
    return " | ".join(p for p in parts if p).lower()


# Driver / library messages that identify a *specific* class. Checked in order:
# the first match wins, so the most specific patterns come first.
_AUTH_MARKERS = (
    "invalid_client",
    "invalid_grant",
    "unauthorized",
    "not authorized",
    "access denied",
    "signaturedoesnotmatch",
    "invalidaccesskeyid",
    "invalidcredentials",
    "invalid credentials",
    "authentication failed",
    "401 ",
    " 401",
    "403 ",
    " 403",
)
_RATE_MARKERS = ("429", "rate limit", "too many requests", "throttl")
_TIMEOUT_MARKERS = ("timeout", "timed out", "readtimeout", "connecttimeout")
_UPSTREAM_MARKERS = ("502", "503", "504", "bad gateway", "service unavailable",
                     "connection reset", "connection refused", "temporary failure")
_DB_MARKERS = (
    "psycopg2",
    "sqlalchemy.exc.operationalerror",
    "could not connect",
    "connection to server",
    "server closed the connection",
    "password authentication failed",
    "statement timeout",
    "lock timeout",
    "querycanceled",
    "deadlock detected",
    "too many connections",
    "tenant or user not found",
)


def classify_exception(exc: BaseException) -> ErrorClass:
    """Map an arbitrary exception onto one of the documented classes.

    Deliberately conservative: only patterns we have actually observed in the
    SaKgaZé stack are matched; everything else becomes ``PROCESSING_ERROR``
    when it smells like a computation bug and ``UNKNOWN_ERROR`` otherwise.
    """
    if isinstance(exc, IngestionError):
        return exc.error_class

    name = _name(exc)
    text = _text(exc)
    haystack = f"{name} {text}"

    # A missing local dependency is a deployment/configuration defect, never a
    # data-quality verdict about upstream observations.
    if isinstance(exc, ImportError) or "no module named" in text:
        return ErrorClass.CONFIGURATION_ERROR
    if "missing" in text and "credential" in text:
        return ErrorClass.CONFIGURATION_ERROR
    if any(m in haystack for m in ("invalid_client", "invalid_grant", "invalidcredentials",
                                   "invalidaccesskeyid", "signaturedoesnotmatch")):
        return ErrorClass.AUTHENTICATION_ERROR
    if "database" in name or any(m in haystack for m in _DB_MARKERS):
        return ErrorClass.DATABASE_UNAVAILABLE
    if any(m in haystack for m in _RATE_MARKERS):
        return ErrorClass.RATE_LIMITED
    if any(m in haystack for m in _TIMEOUT_MARKERS):
        return ErrorClass.NETWORK_TIMEOUT
    if any(m in haystack for m in _UPSTREAM_MARKERS):
        return ErrorClass.UPSTREAM_UNAVAILABLE
    if any(m in haystack for m in _AUTH_MARKERS):
        return ErrorClass.AUTHENTICATION_ERROR
    if "HTTPStatusError".lower() in haystack:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (401, 403):
            return ErrorClass.AUTHENTICATION_ERROR
        if status == 429:
            return ErrorClass.RATE_LIMITED
        if status is not None and 500 <= int(status) < 600:
            return ErrorClass.UPSTREAM_UNAVAILABLE
    if any(m in haystack for m in ("geojson", "invalid geometry", "shapely", "nan", "empty geometry")):
        return ErrorClass.INVALID_SCIENTIFIC_DATA
    if isinstance(exc, (ValueError, KeyError, TypeError, ArithmeticError)):
        return ErrorClass.PROCESSING_ERROR
    return ErrorClass.UNKNOWN_ERROR


def message_for(error_class: ErrorClass) -> str:
    """Short operator-facing sentence (French product, English CI logs)."""
    return {
        ErrorClass.SUCCESS: "ingestion completed",
        ErrorClass.NO_NEW_DATA: "no new observations in the acquisition window",
        ErrorClass.PARTIAL_SUCCESS: "ingestion completed with rejected records",
        ErrorClass.AUTHENTICATION_ERROR: "upstream rejected our credentials",
        ErrorClass.CONFIGURATION_ERROR: "a required setting or credential is missing",
        ErrorClass.UPSTREAM_UNAVAILABLE: "upstream service unavailable",
        ErrorClass.RATE_LIMITED: "upstream rate limit reached",
        ErrorClass.NETWORK_TIMEOUT: "network timeout talking to upstream",
        ErrorClass.DATABASE_UNAVAILABLE: "database unavailable or schema blocked",
        ErrorClass.INVALID_SCIENTIFIC_DATA: "upstream data failed scientific validation",
        ErrorClass.PROCESSING_ERROR: "processing error inside the pipeline",
        ErrorClass.UNKNOWN_ERROR: "unclassified error",
    }[ErrorClass(error_class)]


def result(error_class: ErrorClass, **extra: Any) -> dict:
    payload = {
        "error_class": ErrorClass(error_class).value,
        "retryable": ErrorClass(error_class) in RETRYABLE,
        "message": message_for(error_class),
    }
    payload.update(extra)
    return payload
