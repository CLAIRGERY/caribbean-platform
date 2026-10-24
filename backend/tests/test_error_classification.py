"""Failure-classification tests — the contract behind the CI notification model.

Regression target: the 2026-09/10 incident. Every run died inside ``init_db()``
with ``psycopg2.errors.QueryCanceled: canceling statement due to statement
timeout``. That must classify as ``DATABASE_UNAVAILABLE`` (fatal, non-retryable
as-is) and NOT as an unknown error, and an empty acquisition must classify as a
successful ``NO_NEW_DATA``.
"""
import os
import sys

import httpx
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.src.ingestion.errors import (  # noqa: E402
    EXIT_CODES,
    RETRYABLE,
    ErrorClass,
    IngestionError,
    MissingCredentials,
    classify_exception,
    exit_code,
    result,
)


class FakeOperationalError(Exception):
    """Shape of sqlalchemy.exc.OperationalError: message + .orig."""

    def __init__(self, message, orig=None):
        super().__init__(message)
        self.orig = orig


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://catalogue.dataspace.copernicus.eu/stac/search")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"HTTP {status}", request=request, response=response)


def test_incident_statement_timeout_is_database_unavailable():
    exc = FakeOperationalError(
        "(psycopg2.errors.QueryCanceled) canceling statement due to statement timeout",
        orig=Exception("canceling statement due to statement timeout"),
    )
    assert classify_exception(exc) is ErrorClass.DATABASE_UNAVAILABLE


def test_lock_timeout_is_database_unavailable():
    exc = FakeOperationalError("canceling statement due to lock timeout")
    assert classify_exception(exc) is ErrorClass.DATABASE_UNAVAILABLE


def test_cdse_invalid_credentials_is_authentication_error():
    exc = Exception("CDSE token request failed: {'error': 'invalid_grant'}")
    assert classify_exception(exc) is ErrorClass.AUTHENTICATION_ERROR


def test_s3_signature_mismatch_is_authentication_error():
    exc = Exception("botocore.exceptions.ClientError: SignatureDoesNotMatch for s3://eodata/…")
    assert classify_exception(exc) is ErrorClass.AUTHENTICATION_ERROR


def test_http_401_is_authentication_error_and_not_retryable():
    cls = classify_exception(_http_error(401))
    assert cls is ErrorClass.AUTHENTICATION_ERROR
    assert cls not in RETRYABLE


def test_http_429_is_rate_limited_and_retryable():
    cls = classify_exception(_http_error(429))
    assert cls is ErrorClass.RATE_LIMITED
    assert cls in RETRYABLE


def test_http_503_is_upstream_unavailable():
    assert classify_exception(_http_error(503)) is ErrorClass.UPSTREAM_UNAVAILABLE


def test_timeout_is_network_timeout():
    assert classify_exception(httpx.ConnectTimeout("timed out")) is ErrorClass.NETWORK_TIMEOUT


def test_missing_credential_is_configuration_error():
    exc = MissingCredentials("CDSE_USERNAME", "Copernicus band streaming")
    assert classify_exception(exc) is ErrorClass.CONFIGURATION_ERROR
    assert exc.retryable is False
    assert "CDSE_USERNAME" in exc.message


def test_ingestion_error_keeps_its_class():
    exc = IngestionError(ErrorClass.PROCESSING_ERROR, "boom")
    assert classify_exception(exc) is ErrorClass.PROCESSING_ERROR


def test_unknown_error_falls_back():
    assert classify_exception(RuntimeError("something exotic")) is ErrorClass.UNKNOWN_ERROR


@pytest.mark.parametrize(
    "cls,code",
    [
        (ErrorClass.SUCCESS, 0),
        (ErrorClass.NO_NEW_DATA, 0),
        (ErrorClass.PARTIAL_SUCCESS, 0),
        (ErrorClass.AUTHENTICATION_ERROR, 10),
        (ErrorClass.CONFIGURATION_ERROR, 11),
        (ErrorClass.DATABASE_UNAVAILABLE, 12),
        (ErrorClass.INVALID_SCIENTIFIC_DATA, 13),
        (ErrorClass.UPSTREAM_UNAVAILABLE, 20),
        (ErrorClass.NETWORK_TIMEOUT, 21),
        (ErrorClass.RATE_LIMITED, 22),
        (ErrorClass.PROCESSING_ERROR, 23),
        (ErrorClass.UNKNOWN_ERROR, 29),
    ],
)
def test_exit_codes_are_stable(cls, code):
    """These numbers are referenced by .github/workflows/sakgaze-ingestion.yml."""
    assert EXIT_CODES[cls] == code
    assert exit_code(cls) == code


def test_empty_acquisition_is_not_a_failure():
    payload = result(ErrorClass.NO_NEW_DATA, inserted=0)
    assert payload["error_class"] == "NO_NEW_DATA"
    assert EXIT_CODES[ErrorClass.NO_NEW_DATA] == 0
    assert payload["retryable"] is False
