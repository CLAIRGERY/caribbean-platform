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

from backend.src.database import SargassumDetection, DriftPrediction, MarineAlert


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
