"""Database-level idempotency + status tests for the ingestion layer.

Uses the same dedicated test PostgreSQL/PostGIS database as the e2e suite.
"""
import os
import sys
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.src.database import Base, SargassumDetection, DriftPrediction, MarineAlert
from backend.src import crud
from backend.src.ingestion import common

TEST_DATABASE_URL = "postgresql+psycopg2://ludovic.clairgery:@127.0.0.1:5433/caribbean_platform_test"


@pytest.fixture(scope="module")
def db_session():
    admin = create_engine(
        "postgresql+psycopg2://ludovic.clairgery:@127.0.0.1:5433/postgres",
        isolation_level="AUTOCOMMIT",
    )
    with admin.connect() as conn:
        exists = conn.execute(text(
            "SELECT 1 FROM pg_database WHERE datname='caribbean_platform_test'"
        )).scalar()
        if not exists:
            conn.execute(text("CREATE DATABASE caribbean_platform_test"))
    admin.dispose()

    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()
    engine.dispose()


def _sargassum_feature(acq="2026-08-18T14:57:41+00:00", km2=5.0):
    fid = common.external_id("sargassum", acq, km2, 0.8)
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[-61.5, 16.2], [-61.4, 16.2], [-61.4, 16.3], [-61.5, 16.2]]]},
        "properties": {
            "external_id": fid,
            "surface_km2": km2,
            "density_score": 0.8,
            "density_level": "high",
            "acquisition_date": acq,
            "source_satellite": "S2",
            "source": "cdse_sentinel2",
        },
    }


def test_sargassum_idempotent_no_duplicates(db_session):
    feat = _sargassum_feature()
    first = crud.ingest_sargassum_idempotent(db_session, [feat])
    assert first["inserted"] == 1
    assert first["skipped"] == 0

    second = crud.ingest_sargassum_idempotent(db_session, [feat])
    assert second["inserted"] == 0
    assert second["skipped"] == 1

    count = db_session.query(SargassumDetection).count()
    assert count == 1


def test_sargassum_rollback_on_bad_geometry(db_session):
    bad = {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": "not-a-polygon"},
        "properties": {"external_id": "x", "acquisition_date": "2026-08-18T00:00:00+00:00"},
    }
    result = crud.ingest_sargassum_idempotent(db_session, [bad])
    assert result["inserted"] == 0
    assert result["rejected"] == 1


def test_drift_idempotent(db_session):
    fid = common.external_id("drift", "line", -61.0, 15.0, 24)
    feat = {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [[-61.0, 15.0], [-60.9, 15.1]]},
        "properties": {
            "external_id": fid,
            "prediction_horizon_days": 1,
            "eta_hours": 24.0,
            "landing_probability_pct": 0.0,
            "target_sector": "trajectory",
            "source": "drift_engine",
        },
    }
    a = crud.ingest_drift_idempotent(db_session, [feat])
    b = crud.ingest_drift_idempotent(db_session, [feat])
    assert a["inserted"] == 1
    assert b["inserted"] == 0
    assert b["skipped"] == 1


def test_marine_alert_idempotent(db_session):
    fid = common.external_id("marine", "coastal", "Guadeloupe", "2026-08-19T00")
    feat = {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[-61.6, 16.2], [-61.5, 16.2], [-61.5, 16.3], [-61.6, 16.2]]]},
        "properties": {
            "external_id": fid,
            "alert_type": "marine_conditions",
            "alert_level": "Yellow",
            "sector": "Guadeloupe",
            "issued_at": "2026-08-19T00:00:00+00:00",
            "source": "open_meteo",
        },
    }
    a = crud.ingest_marine_alerts_idempotent(db_session, [feat])
    b = crud.ingest_marine_alerts_idempotent(db_session, [feat])
    assert a["inserted"] == 1
    assert b["inserted"] == 0
    assert b["skipped"] == 1


def test_ingestion_status_and_runs(db_session):
    crud.record_ingestion_run(
        db_session, "sargassum", "success", downloaded=5, inserted=5, skipped=0,
        latest_data=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    status = crud.get_ingestion_status(db_session)
    assert status["status"] == "ok"
    assert "sargassum" in status["sources"]
    assert status["sources"]["sargassum"]["last_success"] is not None
