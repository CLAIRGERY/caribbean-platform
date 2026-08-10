"""
Formal pytest end-to-end integration tests for SaKgaZé / Weathernext.

Uses httpx.AsyncClient against the FastAPI app (in-process) and a dedicated
test PostgreSQL database.  The app lifespan is exercised by wrapping the app
with an ASGI lifespan manager.
"""
import os
import sys
import asyncio
from datetime import datetime, timezone

import pytest
import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Use auto mode so async fixtures and tests share a function-scoped event loop.
pytestmark = pytest.mark.asyncio(loop_scope="function")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.src.database import Base, init_db
from backend.src.main import app
from sakgaze.src.pipeline import run_pipeline as run_sakgaze
from weathernext.src.pipeline import run_pipeline as run_weathernext
from drift.src.engine import run_engine as run_drift

# Use a dedicated test database on the running PostGIS cluster.
TEST_DATABASE_URL = "postgresql+psycopg2://ludovic.clairgery:@127.0.0.1:5433/caribbean_platform_test"


def _create_test_db():
    """Create the test database if it does not exist."""
    admin_url = "postgresql+psycopg2://ludovic.clairgery:@127.0.0.1:5433/postgres"
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", future=True)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1 FROM pg_database WHERE datname='caribbean_platform_test'"))
        if not result.scalar():
            conn.execute(text("CREATE DATABASE caribbean_platform_test"))
    engine.dispose()


def _drop_test_tables():
    """Recreate a clean schema for tests."""
    engine = create_engine(TEST_DATABASE_URL, future=True)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_sargassum_geom ON sargassum_detections USING GIST (geometry);"
            "CREATE INDEX IF NOT EXISTS idx_drift_geom ON drift_predictions USING GIST (geometry);"
            "CREATE INDEX IF NOT EXISTS idx_alerts_geom ON marine_alerts USING GIST (geometry);"
        ))
        conn.commit()
    engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def prepare_test_db():
    _create_test_db()
    _drop_test_tables()
    yield


@pytest.fixture
def test_engine():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True, future=True)
    yield engine
    engine.dispose()


@pytest.fixture
def override_database_url(monkeypatch):
    """Point the app at the test database for the duration of a test."""
    from backend.src import database
    from shared.config import settings

    monkeypatch.setattr(settings, "DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setattr(settings, "SYNC_DATABASE_URL", TEST_DATABASE_URL)

    original_engine = database.engine
    original_session = database.SessionLocal

    new_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True, future=True)
    new_session = sessionmaker(autocommit=False, autoflush=False, bind=new_engine)

    monkeypatch.setattr(database, "engine", new_engine)
    monkeypatch.setattr(database, "SessionLocal", new_session)

    yield

    new_engine.dispose()
    monkeypatch.setattr(database, "engine", original_engine)
    monkeypatch.setattr(database, "SessionLocal", original_session)


@pytest.fixture
async def async_client(override_database_url):
    """Provide an httpx.AsyncClient wired to the FastAPI app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _valid_sargassum_fc():
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-61.5, 16.25],
                            [-61.45, 16.25],
                            [-61.45, 16.30],
                            [-61.5, 16.30],
                            [-61.5, 16.25],
                        ]
                    ],
                },
                "properties": {
                    "surface_km2": 12.5,
                    "density_score": 0.85,
                    "density_level": "high",
                    "acquisition_date": datetime.now(timezone.utc).isoformat(),
                },
            }
        ],
    }


@pytest.mark.asyncio
async def test_health(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_post_sargassum_detections(async_client):
    fc = _valid_sargassum_fc()
    response = await async_client.post("/api/v1/sakgaze/detections", json=fc)
    assert response.status_code == 200
    data = response.json()
    assert data["inserted"] == 1
    assert data["endpoint"] == "/api/v1/sakgaze/detections"
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_post_rejects_invalid_geojson(async_client):
    bad = {"type": "FeatureCollection", "features": "not-a-list"}
    response = await async_client.post("/api/v1/sakgaze/detections", json=bad)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_detections_latest(async_client):
    # Seed data
    await async_client.post("/api/v1/sakgaze/detections", json=_valid_sargassum_fc())
    response = await async_client.get("/api/v1/sakgaze/detections/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) >= 1
    assert data["features"][0]["geometry"]["type"] == "Polygon"


@pytest.mark.asyncio
async def test_post_and_get_marine_alerts(async_client):
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-61.6, 16.2],
                            [-61.5, 16.2],
                            [-61.5, 16.3],
                            [-61.6, 16.3],
                            [-61.6, 16.2],
                        ]
                    ],
                },
                "properties": {
                    "alert_type": "marine_conditions",
                    "alert_level": "Yellow",
                    "sector": "Guadeloupe",
                    "wind_speed_knots": 22.0,
                    "wave_height_m": 2.5,
                    "issued_at": datetime.now(timezone.utc).isoformat(),
                },
            }
        ],
    }
    post = await async_client.post("/api/v1/weathernext/marine-alerts", json=fc)
    assert post.status_code == 200
    assert post.json()["inserted"] == 1

    get = await async_client.get("/api/v1/weathernext/marine-alerts/latest")
    assert get.status_code == 200
    data = get.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) >= 1


@pytest.mark.asyncio
async def test_post_and_get_drift_predictions(async_client):
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-61.5, 16.25], [-61.4, 16.35]],
                },
                "properties": {
                    "prediction_horizon_days": 1,
                    "eta_hours": 24.0,
                    "landing_probability_pct": 45.0,
                    "target_sector": "Guadeloupe",
                },
            }
        ],
    }
    post = await async_client.post("/api/v1/sakgaze/drift-predictions", json=fc)
    assert post.status_code == 200
    assert post.json()["inserted"] == 1

    get = await async_client.get("/api/v1/sakgaze/drift-predictions/latest")
    assert get.status_code == 200
    data = get.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) >= 1


def test_pipeline_functions_produce_geojson():
    """Verify the three pipeline modules return valid FeatureCollections."""
    sak = run_sakgaze()
    assert sak["type"] == "FeatureCollection"
    assert len(sak["features"]) > 0

    wx = run_weathernext()
    assert wx["type"] == "FeatureCollection"
    assert len(wx["features"]) > 0

    drift = run_drift()
    assert drift["type"] == "FeatureCollection"
    assert len(drift["features"]) > 0
