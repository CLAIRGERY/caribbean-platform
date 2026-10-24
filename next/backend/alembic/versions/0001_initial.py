"""initial PostGIS schema

Non-destructive and idempotent by design: the SaKgaZé production database
already contains these tables. Running this revision against an existing
database adds only the columns/indexes that are missing; against an empty
database it creates everything.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-24
"""
from __future__ import annotations

import geoalchemy2
import sqlalchemy as sa
from alembic import context, op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

ADDITIVE_COLUMNS = [
    ("sargassum_detections", "external_id", sa.String(64)),
    ("sargassum_detections", "source", sa.String(50)),
    ("drift_predictions", "external_id", sa.String(64)),
    ("drift_predictions", "source", sa.String(50)),
    ("marine_alerts", "external_id", sa.String(64)),
    ("marine_alerts", "source", sa.String(50)),
]

INDEXES = [
    ("idx_sargassum_geom", "sargassum_detections", "USING GIST (geometry)"),
    ("idx_drift_geom", "drift_predictions", "USING GIST (geometry)"),
    ("idx_alerts_geom", "marine_alerts", "USING GIST (geometry)"),
    ("idx_sargassum_acq_date", "sargassum_detections", "(acquisition_date)"),
    ("idx_drift_created_at", "drift_predictions", "(created_at)"),
    ("idx_alerts_issued_at", "marine_alerts", "(issued_at)"),
    ("idx_sargassum_external_id", "sargassum_detections", "(external_id)"),
    ("idx_drift_external_id", "drift_predictions", "(external_id)"),
    ("idx_alerts_external_id", "marine_alerts", "(external_id)"),
    ("idx_ingestion_runs_source_finished", "ingestion_runs", "(source, finished_at)"),
]


def _existing_tables() -> set:
    """Existing tables, or an empty set in offline (``--sql``) mode.

    Offline mode has no live connection to introspect, so the generated SQL
    describes the *empty database* case. Run the real migration online.
    """
    if context.is_offline_mode():
        return set()
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing_columns(table: str) -> set:
    if context.is_offline_mode():
        return set()
    try:
        return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    except Exception:  # noqa: BLE001 - table may be absent
        return set()


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    tables = _existing_tables()

    if "sargassum_detections" not in tables:
        op.create_table(
            "sargassum_detections",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("external_id", sa.String(64)),
            sa.Column("source", sa.String(50), server_default="cdse_sentinel2"),
            sa.Column("acquisition_date", sa.DateTime, nullable=False),
            sa.Column("surface_km2", sa.Float, nullable=False),
            sa.Column("density_score", sa.Float, nullable=False),
            sa.Column("density_level", sa.String(20), nullable=False),
            sa.Column("source_satellite", sa.String(20), server_default="S2"),
            sa.Column("geometry", geoalchemy2.Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=False),
            sa.Column("properties", sa.JSON),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )

    if "drift_predictions" not in tables:
        op.create_table(
            "drift_predictions",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("external_id", sa.String(64)),
            sa.Column("source", sa.String(50), server_default="drift_engine"),
            sa.Column("prediction_horizon_days", sa.Integer, nullable=False),
            sa.Column("eta_hours", sa.Float, nullable=False),
            sa.Column("landing_probability_pct", sa.Float, nullable=False),
            sa.Column("target_sector", sa.String(50), nullable=False),
            sa.Column("geometry", geoalchemy2.Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=False),
            sa.Column("properties", sa.JSON),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )

    if "marine_alerts" not in tables:
        op.create_table(
            "marine_alerts",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("external_id", sa.String(64)),
            sa.Column("source", sa.String(50), server_default="noaa_nhc_openmeteo"),
            sa.Column("alert_type", sa.String(30), nullable=False),
            sa.Column("alert_level", sa.String(10), nullable=False),
            sa.Column("sector", sa.String(50)),
            sa.Column("event_name", sa.String(50)),
            sa.Column("wind_speed_knots", sa.Float),
            sa.Column("gust_speed_knots", sa.Float),
            sa.Column("wave_height_m", sa.Float),
            sa.Column("wave_period_s", sa.Float),
            sa.Column("h2s_risk", sa.String(10)),
            sa.Column("issued_at", sa.DateTime, nullable=False),
            sa.Column("geometry", geoalchemy2.Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=True),
            sa.Column("properties", sa.JSON),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )

    if "ingestion_runs" not in tables:
        op.create_table(
            "ingestion_runs",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("source", sa.String(30), nullable=False),
            sa.Column("status", sa.String(12), nullable=False),
            sa.Column("started_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
            sa.Column("finished_at", sa.DateTime),
            sa.Column("records_downloaded", sa.Integer, server_default="0"),
            sa.Column("records_inserted", sa.Integer, server_default="0"),
            sa.Column("records_skipped", sa.Integer, server_default="0"),
            sa.Column("records_rejected", sa.Integer, server_default="0"),
            sa.Column("latest_data_timestamp", sa.DateTime),
            sa.Column("error", sa.Text),
        )

    # Additive columns for pre-existing tables (the live production case).
    for table, column, type_ in ADDITIVE_COLUMNS:
        if table in tables and column not in _existing_columns(table):
            op.add_column(table, sa.Column(column, type_))

    # Indexes: IF NOT EXISTS keeps this safe on the live database.
    for name, table, definition in INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} {definition}")


def downgrade() -> None:
    """Intentionally conservative: never drop production science tables."""
    raise RuntimeError(
        "0001_initial has no downgrade: dropping scientific tables requires an "
        "explicit, reviewed manual operation (see docs/new-supabase-setup.md)."
    )
