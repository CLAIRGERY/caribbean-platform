"""PostGIS read layer for the three scientific map layers.

* SQL is built by pure functions (``build_sql``) so the query shape is unit
  testable without a database.
* Geometries are simplified **on delivery only**: ``ST_SimplifyPreserveTopology``
  with a tolerance far below Sentinel-2 resolution. Stored geometry keeps full
  scientific accuracy.
* Every query is bounded by ``LIMIT`` and by a temporal window.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import classify_db_error
from app.schemas.params import LayerQuery


def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.isoformat() + "Z"
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class LayerSpec:
    key: str
    table: str
    time_column: str
    properties: Tuple[str, ...]
    #: Optional column rendered as the feature ``id``.
    id_column: str = "id"


LAYERS: Dict[str, LayerSpec] = {
    "sargassum": LayerSpec(
        key="sargassum",
        table="sargassum_detections",
        time_column="acquisition_date",
        properties=(
            "acquisition_date", "surface_km2", "density_score", "density_level",
            "source_satellite", "source", "external_id",
        ),
    ),
    "drift": LayerSpec(
        key="drift",
        table="drift_predictions",
        time_column="created_at",
        properties=(
            "prediction_horizon_days", "eta_hours", "landing_probability_pct",
            "target_sector", "source", "external_id", "created_at",
        ),
    ),
    "alerts": LayerSpec(
        key="alerts",
        table="marine_alerts",
        time_column="issued_at",
        properties=(
            "issued_at", "alert_type", "alert_level", "sector", "event_name",
            "wind_speed_knots", "gust_speed_knots", "wave_height_m", "wave_period_s",
            "h2s_risk", "source", "external_id",
        ),
    ),
}

_GEOM_SQL = "ST_AsGeoJSON(ST_SimplifyPreserveTopology(geometry, :simplify_tolerance), 6)::json AS geom"


def build_sql(layer: LayerSpec, query: LayerQuery) -> Tuple[str, Dict[str, Any]]:
    """Return (sql, params). All values are bound, never interpolated."""
    params: Dict[str, Any] = {
        "since": query.since,
        "limit": query.limit,
        "offset": query.offset,
    }
    where = [f"{layer.time_column} >= :since"]
    if query.until is not None:
        where.append(f"{layer.time_column} <= :until")
        params["until"] = query.until
    if query.bbox is not None:
        minx, miny, maxx, maxy = query.bbox
        where.append("ST_Intersects(geometry, ST_MakeEnvelope(:minx, :miny, :maxx, :maxy, 4326))")
        params.update({"minx": minx, "miny": miny, "maxx": maxx, "maxy": maxy})
    where.append("geometry IS NOT NULL")

    columns = [layer.id_column] + list(dict.fromkeys(layer.properties + (layer.time_column,)))
    select_cols = ", ".join(columns)
    sql = (
        f"SELECT {select_cols}, properties, {_GEOM_SQL} "
        f"FROM {layer.table} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY {layer.time_column} DESC, {layer.id_column} DESC "
        f"LIMIT :limit OFFSET :offset"
    )
    params["simplify_tolerance"] = 0.0005
    return sql, params


def _row_to_feature(layer: LayerSpec, row: Dict[str, Any]) -> Dict[str, Any]:
    props: Dict[str, Any] = {}
    raw_props = row.get("properties") or {}
    if isinstance(raw_props, dict):
        props.update(raw_props)
    for column in layer.properties:
        value = row.get(column)
        if isinstance(value, datetime):
            value = _iso(value)
        if value is not None:
            props[column] = value
    return {
        "type": "Feature",
        "id": row.get(layer.id_column),
        "geometry": row.get("geom"),
        "properties": props,
    }


class GeospatialRepository:
    """Read-only PostGIS access. One instance per app (stateless)."""

    def __init__(self, simplify_tolerance: float = 0.0005):
        self.simplify_tolerance = simplify_tolerance

    def fetch_layer(self, session: Session, layer_key: str, query: LayerQuery) -> Dict[str, Any]:
        layer = LAYERS[layer_key]
        sql, params = build_sql(layer, query)
        params["simplify_tolerance"] = self.simplify_tolerance
        try:
            rows = [dict(r._mapping) for r in session.execute(text(sql), params)]
        except Exception as exc:  # noqa: BLE001 - classified, never leaked
            session.rollback()
            raise classify_db_error(exc)
        features = [_row_to_feature(layer, row) for row in rows if row.get("geom")]
        latest = self._latest(rows, layer.time_column)
        return {
            "type": "FeatureCollection",
            "features": features,
            "meta": {
                "count": len(features),
                "limit": query.limit,
                "offset": query.offset,
                "days": query.days,
                "bbox": list(query.bbox) if query.bbox else None,
                "until": _iso(query.until),
                "latest_data_timestamp": _iso(latest),
                "simplified": True,
                "simplify_tolerance": self.simplify_tolerance,
                "source": layer.table,
                "generated_at": _iso(datetime.now(timezone.utc)),
            },
        }

    @staticmethod
    def _latest(rows: Sequence[Dict[str, Any]], column: str) -> Optional[datetime]:
        values = [r.get(column) for r in rows if isinstance(r.get(column), datetime)]
        return max(values) if values else None
