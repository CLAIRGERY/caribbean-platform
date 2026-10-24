"""Legacy API surface guards.

The frontend composes every URL as ``VITE_API_BASE_URL + path`` and probes
``/health``. With a ``…/api/v1`` base that becomes ``/api/v1/health``; without an
alias the probe 404s while the data endpoints work, and the UI shows DEGRADED for
a healthy backend. These tests pin the alias on the legacy app too.
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://u:p@127.0.0.1:59999/nodb")


def _legacy_app():
    try:
        from backend.src.main import app
    except Exception as exc:  # noqa: BLE001 - optional deps (geoalchemy2, shapely…)
        pytest.skip(f"legacy app not importable here: {type(exc).__name__}: {exc}")
    return app


def test_health_is_reachable_at_root_and_under_api_v1():
    from fastapi.testclient import TestClient

    client = TestClient(_legacy_app())
    root = client.get("/health")
    versioned = client.get("/api/v1/health")
    assert root.status_code == 200
    assert versioned.status_code == 200
    assert root.json() == versioned.json()
    assert versioned.json()["status"] == "ok"


def test_health_never_touches_the_database():
    """The probe must answer while the DB is unreachable (port 59999 is closed)."""
    from fastapi.testclient import TestClient

    client = TestClient(_legacy_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert "sakgaze-api" in response.json()["service"]
