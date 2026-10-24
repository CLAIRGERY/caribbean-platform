"""Test harness: real HTTP surface, fake persistence.

No PostGIS is required to test the API contract. The repository and the status
service are injected through the app factory, so every test exercises the actual
routing, validation, serialisation, middleware and error handling.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DATABASE_URL", "")
os.environ.setdefault("CORS_ORIGINS", "https://sakgaze.com")

from app.database.session import get_optional_session, get_session  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories.geospatial import LAYERS  # noqa: E402


class FakeSession:
    """Stand-in for a SQLAlchemy session (the fake repository ignores it)."""

    def execute(self, *args, **kwargs):  # pragma: no cover - not used
        raise AssertionError("fake repository must not touch the session")

    def close(self) -> None:
        pass

    def rollback(self) -> None:
        pass


def _feature(index: int, layer: str) -> dict:
    ts = (datetime.now(timezone.utc) - timedelta(hours=index)).isoformat().replace("+00:00", "Z")
    props = {"source": "test", "external_id": f"{layer}-{index}"}
    if layer == "sargassum":
        props.update({"acquisition_date": ts, "surface_km2": 1.25, "density_score": 0.6,
                      "density_level": "medium", "source_satellite": "S2"})
        geometry = {"type": "Polygon", "coordinates": [[[-61.5, 15.2], [-61.4, 15.2],
                                                        [-61.4, 15.3], [-61.5, 15.2]]]}
    elif layer == "drift":
        props.update({"prediction_horizon_days": 3, "eta_hours": 48.0,
                      "landing_probability_pct": 42.0, "target_sector": "martinique"})
        geometry = {"type": "LineString", "coordinates": [[-61.4, 15.1], [-61.2, 15.4]]}
    else:
        props.update({"issued_at": ts, "alert_type": "wind", "alert_level": "Amber",
                      "sector": "guadeloupe", "wind_speed_knots": 22.0})
        geometry = {"type": "Point", "coordinates": [-61.5, 16.2]}
    return {"type": "Feature", "id": index, "geometry": geometry, "properties": props}


class FakeRepository:
    """Returns synthetic *shapes* (never scientific values) for contract testing."""

    def __init__(self, count: int = 3, fail_with: Exception | None = None):
        self.count = count
        self.fail_with = fail_with
        self.calls: list = []

    def fetch_layer(self, session, layer_key, query):
        self.calls.append((layer_key, query))
        if self.fail_with is not None:
            raise self.fail_with
        layer = LAYERS[layer_key]
        features = [_feature(i, layer_key) for i in range(self.count)]
        return {
            "type": "FeatureCollection",
            "features": features,
            "meta": {
                "count": len(features),
                "limit": query.limit,
                "offset": query.offset,
                "days": query.days,
                "bbox": list(query.bbox) if query.bbox else None,
                "until": query.until.isoformat() if query.until else None,
                "latest_data_timestamp": (
                    features[0]["properties"].get("acquisition_date",
                                                  features[0]["properties"].get("issued_at"))
                    if features else None
                ),
                "simplified": True,
                "simplify_tolerance": 0.0005,
                "source": layer.table,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }


class FakeStatusService:
    def __init__(self, payload=None):
        self.payload = payload
        self.calls = 0

    def build(self, session, *, api_version, environment):
        self.calls += 1
        if self.payload is not None:
            return self.payload
        return {
            "status": "ok",
            "api_version": api_version,
            "environment": environment,
            "database": "ok" if session is not None else "not_configured",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": [
                {"key": "sargassum", "label": "Sargassum (Sentinel-2)", "last_success": None,
                 "latest_data_timestamp": None, "record_count": 0, "freshness": "UNAVAILABLE",
                 "age_hours": None, "thresholds_hours": {"live": 48.0, "recent": 168.0},
                 "note": "Sentinel-2 revisit ≈ 5 days"}
            ],
            "latest_runs": [],
            "warnings": [],
        }


def build_client(repository=None, status_service=None) -> TestClient:
    app = create_app(repository=repository or FakeRepository(),
                     status_service=status_service or FakeStatusService())
    app.dependency_overrides[get_session] = lambda: FakeSession()
    app.dependency_overrides[get_optional_session] = lambda: FakeSession()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def repository() -> FakeRepository:
    return FakeRepository()


@pytest.fixture()
def client(repository) -> TestClient:
    return build_client(repository=repository)
