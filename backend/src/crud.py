"""
CRUD helpers for ingesting and reading GeoJSON data from PostGIS.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json

from sqlalchemy.orm import Session
from sqlalchemy import text
from geoalchemy2.shape import to_shape, from_shape
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

from backend.src.database import SargassumDetection, DriftPrediction, MarineAlert, IngestionRun


def _geom_from_feature(feature: Dict[str, Any]):
    geom = shape(feature["geometry"])
    if not geom.is_valid:
        geom = geom.buffer(0)
    return from_shape(geom, srid=4326)


def _feature_from_row(row, geom_col: str = "geometry") -> Optional[Dict[str, Any]]:
    """Build a GeoJSON Feature from a SQLAlchemy row mapping; geometry from ST_AsGeoJSON."""
    props = dict(row["properties"]) if row.get("properties") else {}
    flat = {
        "id": row.get("id"),
        "acquisition_date": row["acquisition_date"].isoformat() + "Z" if row.get("acquisition_date") else None,
        "surface_km2": row.get("surface_km2"),
        "density_score": row.get("density_score"),
        "density_level": row.get("density_level"),
        "source_satellite": row.get("source_satellite"),
        "prediction_horizon_days": row.get("prediction_horizon_days"),
        "eta_hours": row.get("eta_hours"),
        "landing_probability_pct": row.get("landing_probability_pct"),
        "target_sector": row.get("target_sector"),
        "alert_type": row.get("alert_type"),
        "alert_level": row.get("alert_level"),
        "sector": row.get("sector"),
        "event_name": row.get("event_name"),
        "wind_speed_knots": row.get("wind_speed_knots"),
        "gust_speed_knots": row.get("gust_speed_knots"),
        "wave_height_m": row.get("wave_height_m"),
        "wave_period_s": row.get("wave_period_s"),
        "h2s_risk": row.get("h2s_risk"),
        "issued_at": row["issued_at"].isoformat() + "Z" if row.get("issued_at") else None,
    }
    flat.update(props)
    return {
        "type": "Feature",
        "geometry": row["geom_geojson"] if row.get("geom_geojson") else None,
        "properties": flat,
    }


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------
def ingest_sargassum_detections(db: Session, fc: Dict[str, Any]) -> Dict[str, Any]:
    inserted = 0
    errors: List[str] = []
    for idx, f in enumerate(fc.get("features", [])):
        try:
            props = f.get("properties", {})
            acquisition = props.get("acquisition_date")
            if isinstance(acquisition, str):
                acquisition = datetime.fromisoformat(acquisition.replace("Z", "+00:00"))
            rec = SargassumDetection(
                acquisition_date=acquisition or datetime.utcnow(),
                surface_km2=float(props.get("surface_km2", 0.0)),
                density_score=float(props.get("density_score", 0.0)),
                density_level=props.get("density_level", "unknown"),
                source_satellite=props.get("source_satellite", "S2"),
                geometry=_geom_from_feature(f),
                properties=props,
            )
            db.add(rec)
            inserted += 1
        except Exception as exc:
            errors.append(f"feature {idx}: {exc}")
    db.commit()
    return {"inserted": inserted, "endpoint": "/api/v1/sakgaze/detections", "errors": errors}


def ingest_drift_predictions(db: Session, fc: Dict[str, Any]) -> Dict[str, Any]:
    inserted = 0
    errors: List[str] = []
    for idx, f in enumerate(fc.get("features", [])):
        try:
            props = f.get("properties", {})
            rec = DriftPrediction(
                prediction_horizon_days=int(props.get("prediction_horizon_days", 3)),
                eta_hours=float(props.get("eta_hours", 0.0)),
                landing_probability_pct=float(props.get("landing_probability_pct", 0.0)),
                target_sector=props.get("target_sector", "unknown"),
                geometry=_geom_from_feature(f),
                properties=props,
            )
            db.add(rec)
            inserted += 1
        except Exception as exc:
            errors.append(f"feature {idx}: {exc}")
    db.commit()
    return {"inserted": inserted, "endpoint": "/api/v1/sakgaze/drift-predictions", "errors": errors}


def ingest_marine_alerts(db: Session, fc: Dict[str, Any]) -> Dict[str, Any]:
    inserted = 0
    errors: List[str] = []
    for idx, f in enumerate(fc.get("features", [])):
        try:
            props = f.get("properties", {})
            issued = props.get("issued_at")
            if isinstance(issued, str):
                issued = datetime.fromisoformat(issued.replace("Z", "+00:00"))
            geom = None
            if f.get("geometry"):
                geom = _geom_from_feature(f)
            rec = MarineAlert(
                alert_type=props.get("alert_type", "unknown"),
                alert_level=props.get("alert_level", "Green"),
                sector=props.get("sector"),
                event_name=props.get("event_name"),
                wind_speed_knots=props.get("wind_speed_knots"),
                gust_speed_knots=props.get("gust_speed_knots"),
                wave_height_m=props.get("wave_height_m"),
                wave_period_s=props.get("wave_period_s"),
                h2s_risk=props.get("h2s_risk"),
                issued_at=issued or datetime.utcnow(),
                geometry=geom,
                properties=props,
            )
            db.add(rec)
            inserted += 1
        except Exception as exc:
            errors.append(f"feature {idx}: {exc}")
    db.commit()
    return {"inserted": inserted, "endpoint": "/api/v1/weathernext/marine-alerts", "errors": errors}


# ---------------------------------------------------------------------------
# Read (ST_AsGeoJSON optimized)
# ---------------------------------------------------------------------------
def get_latest_sargassum(db: Session, days: int = 7) -> Dict[str, Any]:
    since = datetime.utcnow() - timedelta(days=days)
    sql = text(
        "SELECT id, acquisition_date, surface_km2, density_score, density_level, "
        "source_satellite, properties, ST_AsGeoJSON(geometry)::json AS geom_geojson "
        "FROM sargassum_detections WHERE acquisition_date >= :since "
        "ORDER BY acquisition_date DESC"
    )
    rows = db.execute(sql, {"since": since}).mappings().all()
    return {
        "type": "FeatureCollection",
        "features": [_feature_from_row(r) for r in rows if r["geom_geojson"]],
    }


def get_latest_marine_alerts(db: Session, days: int = 7) -> Dict[str, Any]:
    since = datetime.utcnow() - timedelta(days=days)
    sql = text(
        "SELECT id, alert_type, alert_level, sector, event_name, wind_speed_knots, "
        "gust_speed_knots, wave_height_m, wave_period_s, h2s_risk, issued_at, "
        "properties, ST_AsGeoJSON(geometry)::json AS geom_geojson "
        "FROM marine_alerts WHERE issued_at >= :since "
        "ORDER BY issued_at DESC"
    )
    rows = db.execute(sql, {"since": since}).mappings().all()
    return {
        "type": "FeatureCollection",
        "features": [_feature_from_row(r) for r in rows if r["geom_geojson"]],
    }


def get_latest_drift_predictions(db: Session, days: int = 7) -> Dict[str, Any]:
    since = datetime.utcnow() - timedelta(days=days)
    sql = text(
        "SELECT id, prediction_horizon_days, eta_hours, landing_probability_pct, "
        "target_sector, properties, created_at, ST_AsGeoJSON(geometry)::json AS geom_geojson "
        "FROM drift_predictions WHERE created_at >= :since "
        "ORDER BY created_at DESC"
    )
    rows = db.execute(sql, {"since": since}).mappings().all()
    return {
        "type": "FeatureCollection",
        "features": [_feature_from_row(r) for r in rows if r["geom_geojson"]],
    }


# ---------------------------------------------------------------------------
# Idempotent ingestion (external_id deduplication + run metadata)
# ---------------------------------------------------------------------------
def _existing_external_ids(db: Session, model, ids: List[str]) -> set:
    """Return the subset of external_ids already present for a model."""
    if not ids:
        return set()
    col = model.__table__.c.external_id
    rows = db.query(model.external_id).filter(col.in_(ids)).all()
    return {r[0] for r in rows if r[0]}


def ingest_sargassum_idempotent(db: Session, features: List[Dict[str, Any]]) -> Dict[str, Any]:
    ids = [f.get("properties", {}).get("external_id") for f in features]
    ids = [i for i in ids if i]
    existing = _existing_external_ids(db, SargassumDetection, ids)
    inserted = skipped = rejected = 0
    for f in features:
        props = f.get("properties", {})
        fid = props.get("external_id")
        if fid and fid in existing:
            skipped += 1
            continue
        try:
            acquisition = props.get("acquisition_date")
            if isinstance(acquisition, str):
                acquisition = datetime.fromisoformat(acquisition.replace("Z", "+00:00"))
            rec = SargassumDetection(
                external_id=fid,
                source=props.get("source", "cdse_sentinel2"),
                acquisition_date=acquisition or datetime.utcnow(),
                surface_km2=float(props.get("surface_km2", 0.0)),
                density_score=float(props.get("density_score", 0.0)),
                density_level=props.get("density_level", "unknown"),
                source_satellite=props.get("source_satellite", "S2"),
                geometry=_geom_from_feature(f),
                properties=props,
            )
            db.add(rec)
            inserted += 1
        except Exception:
            rejected += 1
    db.commit()
    return {"inserted": inserted, "skipped": skipped, "rejected": rejected}


def ingest_drift_idempotent(db: Session, features: List[Dict[str, Any]]) -> Dict[str, Any]:
    ids = [f.get("properties", {}).get("external_id") for f in features]
    ids = [i for i in ids if i]
    existing = _existing_external_ids(db, DriftPrediction, ids)
    inserted = skipped = rejected = 0
    for f in features:
        props = f.get("properties", {})
        fid = props.get("external_id")
        if fid and fid in existing:
            skipped += 1
            continue
        try:
            rec = DriftPrediction(
                external_id=fid,
                source=props.get("source", "drift_engine"),
                prediction_horizon_days=int(props.get("prediction_horizon_days", 3)),
                eta_hours=float(props.get("eta_hours", 0.0)),
                landing_probability_pct=float(props.get("landing_probability_pct", 0.0)),
                target_sector=props.get("target_sector", "unknown"),
                geometry=_geom_from_feature(f),
                properties=props,
            )
            db.add(rec)
            inserted += 1
        except Exception:
            rejected += 1
    db.commit()
    return {"inserted": inserted, "skipped": skipped, "rejected": rejected}


def ingest_marine_alerts_idempotent(db: Session, features: List[Dict[str, Any]]) -> Dict[str, Any]:
    ids = [f.get("properties", {}).get("external_id") for f in features]
    ids = [i for i in ids if i]
    existing = _existing_external_ids(db, MarineAlert, ids)
    inserted = skipped = rejected = 0
    for f in features:
        props = f.get("properties", {})
        fid = props.get("external_id")
        if fid and fid in existing:
            skipped += 1
            continue
        try:
            issued = props.get("issued_at")
            if isinstance(issued, str):
                issued = datetime.fromisoformat(issued.replace("Z", "+00:00"))
            geom = None
            if f.get("geometry"):
                geom = _geom_from_feature(f)
            rec = MarineAlert(
                external_id=fid,
                source=props.get("source", "noaa_nhc_openmeteo"),
                alert_type=props.get("alert_type", "unknown"),
                alert_level=props.get("alert_level", "Green"),
                sector=props.get("sector"),
                event_name=props.get("event_name"),
                wind_speed_knots=props.get("wind_speed_knots"),
                gust_speed_knots=props.get("gust_speed_knots"),
                wave_height_m=props.get("wave_height_m"),
                wave_period_s=props.get("wave_period_s"),
                h2s_risk=props.get("h2s_risk"),
                issued_at=issued or datetime.utcnow(),
                geometry=geom,
                properties=props,
            )
            db.add(rec)
            inserted += 1
        except Exception:
            rejected += 1
    db.commit()
    return {"inserted": inserted, "skipped": skipped, "rejected": rejected}


# ---------------------------------------------------------------------------
# Ingestion run metadata + status
# ---------------------------------------------------------------------------
def record_ingestion_run(
    db: Session,
    source: str,
    status: str,
    *,
    downloaded: int = 0,
    inserted: int = 0,
    skipped: int = 0,
    rejected: int = 0,
    latest_data: Optional[datetime] = None,
    error: Optional[str] = None,
) -> None:
    run = IngestionRun(
        source=source,
        status=status,
        finished_at=datetime.utcnow(),
        records_downloaded=downloaded,
        records_inserted=inserted,
        records_skipped=skipped,
        records_rejected=rejected,
        latest_data_timestamp=latest_data,
        error=error,
    )
    db.add(run)
    db.commit()


def get_ingestion_status(db: Session) -> Dict[str, Any]:
    """Latest successful run + record counts per source."""
    from sqlalchemy import func
    sources = {
        "sargassum": ("sargassum_detections", "acquisition_date"),
        "drift_predictions": ("drift_predictions", "created_at"),
        "marine_alerts": ("marine_alerts", "issued_at"),
    }
    result: Dict[str, Any] = {"status": "ok", "sources": {}}
    for key, (table, ts_col) in sources.items():
        # Latest ingestion run
        run = (
            db.query(IngestionRun)
            .filter(IngestionRun.source == key, IngestionRun.status == "success")
            .order_by(IngestionRun.finished_at.desc())
            .first()
        )
        # Latest data + count
        latest = db.execute(text(
            f"SELECT MAX({ts_col}) AS ts, COUNT(*) AS n FROM {table}"
        )).mappings().first()
        result["sources"][key] = {
            "last_success": run.finished_at.isoformat() + "Z" if run and run.finished_at else None,
            "latest_data_timestamp": latest["ts"].isoformat() + "Z" if latest and latest["ts"] else None,
            "record_count": int(latest["n"]) if latest and latest["n"] is not None else 0,
        }
    return result


def latest_acquisition_timestamp(db: Session, table: str, ts_col: str) -> Optional[datetime]:
    row = db.execute(text(f"SELECT MAX({ts_col}) AS ts FROM {table}")).mappings().first()
    return row["ts"] if row else None
