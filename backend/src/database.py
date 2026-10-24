"""
SQLAlchemy + GeoAlchemy2 database setup for the Caribbean platform.
Supports PostGIS geometry columns and async/sync operations.
"""
import os
from datetime import datetime
from typing import Generator

from sqlalchemy import create_engine, event, Column, Integer, String, Float, DateTime, JSON, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from geoalchemy2 import Geometry

DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    # Fallback : conserver la compatibilité avec shared.config.settings (dev local)
    from shared.config.settings import DATABASE_URL as _FALLBACK_URL
    DATABASE_URL = _FALLBACK_URL

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={
        "connect_timeout": 8,
        "application_name": "sakgaze-api",
    },
)


@event.listens_for(engine, "connect")
def _apply_session_limits(dbapi_connection, connection_record):  # noqa: ANN001
    """Bound every session at the SQL level.

    The libpq ``options`` startup parameter is silently ignored by the Supabase
    transaction pooler (pgbouncer), which is why the previous attempt to set
    ``statement_timeout`` via ``connect_args`` had no effect and blocked tables
    hung for minutes. An explicit ``SET`` always reaches the server.
    """
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("SET statement_timeout = '8s'")
        cursor.execute("SET lock_timeout = '5s'")
        cursor.execute("SET idle_in_transaction_session_timeout = '30s'")
        cursor.close()
    except Exception:  # noqa: BLE001 - never block a connection on tuning
        pass


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Optionally create tables/indexes. **DDL is OFF by default.**

    Boot safety + incident safety: running ``ALTER TABLE`` / ``CREATE INDEX``
    from the API process is what deadlocked the schema in September 2026 (a
    cancelled run kept an ACCESS EXCLUSIVE lock and every later run queued
    behind it until the pooler killed it). Schema changes are now applied by an
    explicit, bounded maintenance step::

        python -m backend.src.db_admin --migrate

    Set ``SAKGAZE_AUTO_MIGRATE=1`` only for throwaway/dev databases.
    ``create_all`` is still safe (it checks the catalogue and creates missing
    tables), but it also issues DDL, so it obeys the same switch.
    """
    import logging

    logger = logging.getLogger("sakgaze.database")
    if os.getenv("SAKGAZE_AUTO_MIGRATE", "0") not in ("1", "true", "True", "yes"):
        logger.info("init_db: automatic schema management disabled (SAKGAZE_AUTO_MIGRATE=0)")
        return

    try:
        Base.metadata.create_all(bind=engine)
        _create_spatial_indexes()
        _apply_migrations()
    except Exception as exc:  # noqa: BLE001
        logger.warning("init_db skipped: %s; boot continues without schema DDL", exc)


def _apply_migrations() -> None:
    """Idempotent column migrations for pre-existing production tables."""
    from sqlalchemy import text
    migrations = [
        "ALTER TABLE sargassum_detections ADD COLUMN IF NOT EXISTS external_id VARCHAR(64);",
        "ALTER TABLE sargassum_detections ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'cdse_sentinel2';",
        "ALTER TABLE drift_predictions ADD COLUMN IF NOT EXISTS external_id VARCHAR(64);",
        "ALTER TABLE drift_predictions ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'drift_engine';",
        "ALTER TABLE marine_alerts ADD COLUMN IF NOT EXISTS external_id VARCHAR(64);",
        "ALTER TABLE marine_alerts ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'noaa_nhc_openmeteo';",
        "CREATE INDEX IF NOT EXISTS idx_sargassum_external_id ON sargassum_detections (external_id);",
        "CREATE INDEX IF NOT EXISTS idx_drift_external_id ON drift_predictions (external_id);",
        "CREATE INDEX IF NOT EXISTS idx_alerts_external_id ON marine_alerts (external_id);",
    ]
    with engine.connect() as conn:
        for stmt in migrations:
            conn.execute(text(stmt))
        conn.commit()


def _create_spatial_indexes() -> None:
    """Add GIST spatial indexes for fast map tile / GeoJSON queries."""
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_sargassum_geom "
            "ON sargassum_detections USING GIST (geometry);"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_drift_geom "
            "ON drift_predictions USING GIST (geometry);"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_alerts_geom "
            "ON marine_alerts USING GIST (geometry);"
        ))
        conn.commit()


class SargassumDetection(Base):
    __tablename__ = "sargassum_detections"
    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(64), index=True, nullable=True)
    source = Column(String(50), default="cdse_sentinel2")
    acquisition_date = Column(DateTime, index=True, nullable=False)
    surface_km2 = Column(Float, nullable=False)
    density_score = Column(Float, nullable=False)
    density_level = Column(String(20), nullable=False)
    source_satellite = Column(String(20), default="S2")
    geometry = Column(Geometry("POLYGON", srid=4326), nullable=False)
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DriftPrediction(Base):
    __tablename__ = "drift_predictions"
    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(64), index=True, nullable=True)
    source = Column(String(50), default="drift_engine")
    prediction_horizon_days = Column(Integer, nullable=False)
    eta_hours = Column(Float, nullable=False)
    landing_probability_pct = Column(Float, nullable=False)
    target_sector = Column(String(50), index=True, nullable=False)
    geometry = Column(Geometry("GEOMETRY", srid=4326), nullable=False)
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class MarineAlert(Base):
    __tablename__ = "marine_alerts"
    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(64), index=True, nullable=True)
    source = Column(String(50), default="noaa_nhc_openmeteo")
    alert_type = Column(String(30), index=True, nullable=False)
    alert_level = Column(String(10), nullable=False)
    sector = Column(String(50), index=True, nullable=True)
    event_name = Column(String(50), nullable=True)
    wind_speed_knots = Column(Float, nullable=True)
    gust_speed_knots = Column(Float, nullable=True)
    wave_height_m = Column(Float, nullable=True)
    wave_period_s = Column(Float, nullable=True)
    h2s_risk = Column(String(10), nullable=True)
    issued_at = Column(DateTime, nullable=False)
    geometry = Column(Geometry("GEOMETRY", srid=4326), nullable=True)
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(30), index=True, nullable=False)
    status = Column(String(12), nullable=False)  # success | partial | failed
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    records_downloaded = Column(Integer, default=0)
    records_inserted = Column(Integer, default=0)
    records_skipped = Column(Integer, default=0)
    records_rejected = Column(Integer, default=0)
    latest_data_timestamp = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
