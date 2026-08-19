"""
SQLAlchemy + GeoAlchemy2 database setup for the Caribbean platform.
Supports PostGIS geometry columns and async/sync operations.
"""
import os
import re
from datetime import datetime
from typing import Generator

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from geoalchemy2 import Geometry

DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    # Fallback : conserver la compatibilité avec shared.config.settings (dev local)
    from shared.config.settings import DATABASE_URL as _FALLBACK_URL
    DATABASE_URL = _FALLBACK_URL


# Supabase direct connections resolve to IPv6-only (db.<ref>.supabase.co:5432).
# GitHub Actions / Render runners have no IPv6, so the direct URL fails with
# "Network is unreachable". The shared pooler (Supavisor) is IPv4-only and
# identifies the tenant via the username prefix "postgres.<ref>".
# This rewrites a direct Supabase URL to the pooler while preserving the
# password byte-for-byte (no urlsplit round-trip that could corrupt it).
_SUPABASE_DIRECT_RE = re.compile(
    r'^(?P<scheme>postgres(?:ql)?(?:\+psycopg2)?://)'
    r'postgres(?:\.[a-z0-9]{20})?'
    r'(?P<creds>:[^@]*)'
    r'@db\.(?P<ref>[a-z0-9]{20})\.supabase\.co:5432'
    r'(?P<rest>/.*)?$'
)


def _supabase_pooler_url(url: str, region: str = "eu-west-3") -> str:
    """Convert a Supabase direct-connection URL to the IPv4 pooler URL."""
    m = _SUPABASE_DIRECT_RE.match(url)
    if not m:
        return url
    scheme = m.group("scheme")
    ref = m.group("ref")
    creds = m.group("creds")
    rest = m.group("rest") or "/postgres"
    return f"{scheme}postgres.{ref}{creds}@aws-0-{region}.pooler.supabase.com:6543{rest}"


if "supabase.co" in DATABASE_URL and "pooler.supabase.com" not in DATABASE_URL:
    _converted = _supabase_pooler_url(DATABASE_URL)
    if _converted != DATABASE_URL:
        import logging
        logging.getLogger("sakgaze").warning(
            "Rewrote DATABASE_URL from direct Supabase IPv6 host to IPv4 pooler."
        )
        DATABASE_URL = _converted

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables, PostGIS extension, and spatial GIST indexes."""
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    _create_spatial_indexes()
    _apply_migrations()


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
