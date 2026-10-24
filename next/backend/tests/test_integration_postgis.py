"""Live PostGIS integration test.

Skipped unless ``TEST_DATABASE_URL`` (or ``DATABASE_URL``) points at a PostGIS
database. Read-only: it never writes, never migrates, never drops.
"""
from __future__ import annotations

import os

import pytest

PG_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or ""

pytestmark = pytest.mark.skipif(not PG_URL, reason="no PostGIS database configured")


@pytest.fixture(scope="module")
def engine():
    from sqlalchemy import create_engine

    eng = create_engine(PG_URL, pool_pre_ping=True, connect_args={"connect_timeout": 8})
    try:
        with eng.connect() as conn:
            from sqlalchemy import text

            conn.execute(text("SELECT postgis_version()"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"database not reachable / PostGIS unavailable: {type(exc).__name__}")
    yield eng
    eng.dispose()


def test_layers_query_against_real_postgis(engine):
    from sqlalchemy.orm import sessionmaker

    from app.repositories.geospatial import GeospatialRepository
    from app.schemas.params import build_layer_query

    session = sessionmaker(bind=engine)()
    try:
        repo = GeospatialRepository()
        for layer in ("sargassum", "drift", "alerts"):
            query = build_layer_query(days=90, limit=5, offset=0, bbox=None, until=None,
                                      max_limit=10, default_limit=5, max_days=90)
            payload = repo.fetch_layer(session, layer, query)
            assert payload["type"] == "FeatureCollection"
            assert payload["meta"]["count"] <= 5
            for feature in payload["features"]:
                assert feature["geometry"] is not None
    finally:
        session.close()


def test_status_service_against_real_postgis(engine):
    from sqlalchemy.orm import sessionmaker

    from app.services.status import StatusService

    session = sessionmaker(bind=engine)()
    try:
        payload = StatusService().build(session, api_version="2.0.0", environment="test")
        assert payload["database"] in ("ok", "unavailable")
        assert len(payload["sources"]) == 3
    finally:
        session.close()
