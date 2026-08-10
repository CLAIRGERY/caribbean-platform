"""
SQLAlchemy + GeoAlchemy2 database setup for the Caribbean platform.
Supports PostGIS geometry columns and async/sync operations.
"""
import os
from datetime import datetime
from typing import Generator

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from geoalchemy2 import Geometry

DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    # Fallback : conserver la compatibilité avec shared.config.settings
    from shared.config.settings import DATABASE_URL as _FALLBACK_URL
    DATABASE_URL = _FALLBACK_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
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
