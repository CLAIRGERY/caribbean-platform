"""SQLAlchemy models — PostGIS schema for the SaKgaZé v2 API.

Deliberately identical table/column names to the v1 production schema so the new
backend can run against the current database without a destructive migration.
Additive columns used by the ingestion layer (external_id, source) are part of
the initial Alembic revision.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SargassumDetection(Base):
    __tablename__ = "sargassum_detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(50), default="cdse_sentinel2")
    acquisition_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    surface_km2: Mapped[float] = mapped_column(Float, nullable=False)
    density_score: Mapped[float] = mapped_column(Float, nullable=False)
    density_level: Mapped[str] = mapped_column(String(20), nullable=False)
    source_satellite: Mapped[str] = mapped_column(String(20), default="S2")
    geometry = mapped_column(Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=False)
    props = mapped_column("properties", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default=func.now())

    __table_args__ = (
        Index("idx_sargassum_geom", "geometry", postgresql_using="gist"),
        Index("idx_sargassum_acq_date", "acquisition_date"),
        Index("idx_sargassum_external_id", "external_id"),
    )


class DriftPrediction(Base):
    __tablename__ = "drift_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(50), default="drift_engine")
    prediction_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    eta_hours: Mapped[float] = mapped_column(Float, nullable=False)
    landing_probability_pct: Mapped[float] = mapped_column(Float, nullable=False)
    target_sector: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    geometry = mapped_column(Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=False)
    props = mapped_column("properties", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_drift_geom", "geometry", postgresql_using="gist"),
        Index("idx_drift_created_at", "created_at"),
    )


class MarineAlert(Base):
    __tablename__ = "marine_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(50), default="noaa_nhc_openmeteo")
    alert_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    alert_level: Mapped[str] = mapped_column(String(10), nullable=False)
    sector: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    event_name: Mapped[Optional[str]] = mapped_column(String(50))
    wind_speed_knots: Mapped[Optional[float]] = mapped_column(Float)
    gust_speed_knots: Mapped[Optional[float]] = mapped_column(Float)
    wave_height_m: Mapped[Optional[float]] = mapped_column(Float)
    wave_period_s: Mapped[Optional[float]] = mapped_column(Float)
    h2s_risk: Mapped[Optional[str]] = mapped_column(String(10))
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    geometry = mapped_column(Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=True)
    props = mapped_column("properties", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_alerts_geom", "geometry", postgresql_using="gist"),
        Index("idx_alerts_issued_at", "issued_at"),
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    records_downloaded: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0)
    latest_data_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime)
    error: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (Index("idx_ingestion_runs_source_finished", "source", "finished_at"),)
