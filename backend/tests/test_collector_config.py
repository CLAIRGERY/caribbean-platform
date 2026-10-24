"""Collector configuration guards.

A missing credential must surface as CONFIGURATION_ERROR — never as an empty
acquisition. Mixing the two is what made the 2026 incident invisible for weeks.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.src.ingestion import sargassum  # noqa: E402
from backend.src.ingestion.errors import ErrorClass, MissingCredentials, classify_exception  # noqa: E402


def test_missing_oauth_credentials_raise(monkeypatch):
    monkeypatch.setattr(sargassum, "CDSE_USERNAME", "")
    monkeypatch.setattr(sargassum, "CDSE_PASSWORD", "")
    with pytest.raises(MissingCredentials) as exc:
        sargassum.fetch_sargassum_detections()
    assert "CDSE_USERNAME" in exc.value.message
    assert classify_exception(exc.value) is ErrorClass.CONFIGURATION_ERROR
    assert exc.value.retryable is False


def test_missing_s3_keys_raise(monkeypatch):
    monkeypatch.setattr(sargassum, "CDSE_USERNAME", "user@example.org")
    monkeypatch.setattr(sargassum, "CDSE_PASSWORD", "not-a-real-password")
    monkeypatch.setattr(sargassum, "CDSE_S3_ACCESS_KEY", "")
    monkeypatch.setattr(sargassum, "CDSE_S3_SECRET_KEY", "")
    with pytest.raises(MissingCredentials) as exc:
        sargassum.fetch_sargassum_detections()
    assert "CDSE_S3_ACCESS_KEY" in exc.value.message


def test_collector_never_returns_synthetic_data(monkeypatch):
    """No credential path may fabricate observations."""
    monkeypatch.setattr(sargassum, "CDSE_USERNAME", "")
    monkeypatch.setattr(sargassum, "CDSE_PASSWORD", "")
    with pytest.raises(MissingCredentials):
        sargassum.fetch_sargassum_detections()
