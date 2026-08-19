"""Drift prediction collector.

Physics: V_drift = 0.03 * V_wind + 1.0 * V_current (existing engine formula).

Sources (public, no credentials):
- Open-Meteo Marine API → ocean current velocity/direction.
- Open-Meteo Forecast API → 10m wind (the Marine API does NOT expose wind).

Input sargassum polygons come from the latest detections already in the
database (or a freshly-run sargassum collector). Each detection centroid is
advected forward 24/48/72 h; landing impact cones and per-sector probability
are computed geometrically against the coastal sector footprints.

No synthetic trajectories are ever produced — if there are no detections or
environmental vectors, the collector returns empty.
"""
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from shapely.geometry import LineString, Polygon, mapping, shape

from backend.src.ingestion import common
from backend.src.ingestion.marine_alerts import (
    COASTAL_SECTORS,
    OPEN_METEO_FORECAST_URL,
    OPEN_METEO_MARINE_URL,
    _max,
    _mean,
    _sector_polygon,
)

R_EARTH_M = 6_371_000.0
HORIZONS_HOURS = [24, 48, 72]


def _fetch_marine_batch(coords: List[Tuple[float, float]]) -> List[Dict[str, Optional[float]]]:
    """One Open-Meteo Marine call for many coordinates → per-location summaries."""
    if not coords:
        return []
    data = common.fetch_json(
        OPEN_METEO_MARINE_URL,
        params={
            "latitude": ",".join(f"{c[0]}" for c in coords),
            "longitude": ",".join(f"{c[1]}" for c in coords),
            "hourly": "wave_height,wave_period,ocean_current_velocity,ocean_current_direction",
            "forecast_days": 3,
            "timezone": "UTC",
        },
    )
    locs = data if isinstance(data, list) else [data]
    out: List[Dict[str, Optional[float]]] = []
    for d in locs:
        hourly = d.get("hourly", {})
        out.append({
            "wave_height_m": _max(hourly.get("wave_height")),
            "wave_period_s": _max(hourly.get("wave_period")),
            "current_speed_kmh": _mean(hourly.get("ocean_current_velocity")),
            "current_direction_deg": _mean(hourly.get("ocean_current_direction")),
        })
    while len(out) < len(coords):
        out.append({"wave_height_m": None, "wave_period_s": None,
                    "current_speed_kmh": None, "current_direction_deg": None})
    return out[: len(coords)]


def _fetch_wind_batch(coords: List[Tuple[float, float]]) -> List[Dict[str, Optional[float]]]:
    """One Open-Meteo Forecast call for many coordinates → per-location summaries."""
    if not coords:
        return []
    data = common.fetch_json(
        OPEN_METEO_FORECAST_URL,
        params={
            "latitude": ",".join(f"{c[0]}" for c in coords),
            "longitude": ",".join(f"{c[1]}" for c in coords),
            "hourly": "wind_speed_10m,wind_gusts_10m,wind_direction_10m",
            "forecast_days": 3,
            "timezone": "UTC",
        },
    )
    locs = data if isinstance(data, list) else [data]
    out: List[Dict[str, Optional[float]]] = []
    for d in locs:
        hourly = d.get("hourly", {})
        speed_kmh = _max(hourly.get("wind_speed_10m"))
        gust_kmh = _max(hourly.get("wind_gusts_10m"))
        out.append({
            "wind_speed_knots": speed_kmh * 0.539957 if speed_kmh else None,
            "gust_speed_knots": gust_kmh * 0.539957 if gust_kmh else None,
            "wind_direction_deg": _mean(hourly.get("wind_direction_10m")),
        })
    while len(out) < len(coords):
        out.append({"wind_speed_knots": None, "gust_speed_knots": None,
                    "wind_direction_deg": None})
    return out[: len(coords)]


def fetch_drift_predictions(detections: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Advect sargassum centroids and emit drift lines + impact cones."""
    logger = common.logger
    if detections is None:
        detections = _load_recent_detections()

    if not detections:
        logger.warning("[DRIFT] No sargassum detections available — cannot advect.")
        return []

    # Cap seed detections so Open-Meteo API call volume stays bounded. A single
    # 1414-patch scene would otherwise issue ~2 HTTP calls per seed and blow the
    # workflow timeout. Advect the largest patches first (most impactful).
    n_loaded = len(detections)
    max_seeds = int(os.getenv("DRIFT_MAX_SEEDS", "100"))
    if n_loaded > max_seeds:
        detections = sorted(
            detections,
            key=lambda d: float((d.get("properties") or {}).get("surface_km2") or 0.0),
            reverse=True,
        )[:max_seeds]
        logger.info(
            "[DRIFT] %d detections loaded; advecting top %d by surface area",
            n_loaded, max_seeds,
        )

    # Build seed list (centroid lon/lat + properties).
    seeds: List[Tuple[float, float, Dict[str, Any]]] = []
    for det in detections:
        geom = det.get("geometry")
        if not isinstance(geom, dict):
            continue
        try:
            g = shape(geom)
        except Exception:  # noqa: BLE001
            continue
        centroid = g.centroid
        seeds.append((centroid.x, centroid.y, det.get("properties", {})))

    if not seeds:
        return []

    # Batch-fetch environmental vectors (2 API calls total for all seeds).
    coords = [(s[0], s[1]) for s in seeds]
    try:
        marine_list = _fetch_marine_batch(coords)
        wind_list = _fetch_wind_batch(coords)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DRIFT] Environmental batch fetch failed: %s", exc)
        return []

    features: List[Dict[str, Any]] = []
    for (lon0, lat0, props), marine, wind in zip(seeds, marine_list, wind_list):
        try:
            u, v = _drift_velocity(wind, marine)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[DRIFT] No environmental vector for (%.2f, %.2f): %s", lon0, lat0, exc)
            continue

        for horizon in HORIZONS_HOURS:
            line = _advect(lon0, lat0, u, v, horizon)
            cone = _impact_cone(line)
            for sector_name, info in COASTAL_SECTORS.items():
                sec = _sector_polygon(info)
                prob = _landing_probability(cone, sec, horizon)
                if prob <= 0:
                    continue
                h2s = _h2s_flag(
                    props.get("density_level", "low"),
                    props.get("density_score", 0.0),
                    wind.get("wind_speed_knots"),
                )
                fid = common.external_id(
                    "drift", "cone", round(lon0, 5), round(lat0, 5),
                    horizon, sector_name, common.now_iso()[:13],
                )
                features.append({
                    "type": "Feature",
                    "geometry": mapping(cone),
                    "properties": {
                        "prediction_horizon_days": horizon // 24,
                        "eta_hours": float(horizon),
                        "landing_probability_pct": prob,
                        "target_sector": sector_name,
                        "origin_lon": round(lon0, 5),
                        "origin_lat": round(lat0, 5),
                        "source_density_level": props.get("density_level"),
                        "source_surface_km2": props.get("surface_km2"),
                        "h2s_risk": h2s,
                        "feature_type": "impact_cone",
                        "source": "drift_engine",
                        "external_id": fid,
                        "generated_at": common.now_iso(),
                    },
                })
            # Trajectory line
            fid = common.external_id(
                "drift", "line", round(lon0, 5), round(lat0, 5), horizon, common.now_iso()[:13],
            )
            features.append({
                "type": "Feature",
                "geometry": mapping(line),
                "properties": {
                    "prediction_horizon_days": horizon // 24,
                    "eta_hours": float(horizon),
                    "landing_probability_pct": 0.0,
                    "target_sector": "trajectory",
                    "origin_lon": round(lon0, 5),
                    "origin_lat": round(lat0, 5),
                    "feature_type": "drift_line",
                    "source": "drift_engine",
                    "external_id": fid,
                    "generated_at": common.now_iso(),
                },
            })

    logger.info("[DRIFT] Generated %d drift features", len(features))
    return features


def _load_recent_detections() -> List[Dict[str, Any]]:
    """Load the latest sargassum detections from the database."""
    try:
        from backend.src.database import SessionLocal
        from backend.src.crud import get_latest_sargassum
        db = SessionLocal()
        try:
            fc = get_latest_sargassum(db, days=7)
            return fc.get("features", [])
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        common.logger.warning("[DRIFT] Could not load detections from DB: %s", exc)
        return []


def _drift_velocity(wind: Dict[str, Optional[float]], marine: Dict[str, Optional[float]]) -> Tuple[float, float]:
    # wind: knots → m/s, direction: meteorological degrees (from)
    wind_kts = wind.get("wind_speed_knots") or 0.0
    wind_dir = wind.get("wind_direction_deg") or 0.0
    wind_ms = wind_kts * 0.514444
    wu, wv = _bearing_components(wind_ms, wind_dir)

    # current: km/h → m/s
    cur_kmh = marine.get("current_speed_kmh") or 0.0
    cur_dir = marine.get("current_direction_deg") or 0.0
    cur_ms = cur_kmh / 3.6
    cu, cv = _bearing_components(cur_ms, cur_dir)

    u = 0.03 * wu + 1.0 * cu
    v = 0.03 * wv + 1.0 * cv
    return u, v


def _bearing_components(speed_ms: float, bearing_deg: float) -> Tuple[float, float]:
    rad = math.radians(bearing_deg)
    return speed_ms * math.sin(rad), speed_ms * math.cos(rad)


def _advect(lon: float, lat: float, u: float, v: float, hours: int) -> LineString:
    coords = [(lon, lat)]
    for _ in range(1, hours + 1):
        dx = u * 3600.0
        dy = v * 3600.0
        dlat = (dy / R_EARTH_M) * (180.0 / math.pi)
        dlon = (dx / (R_EARTH_M * math.cos(math.radians(lat)))) * (180.0 / math.pi)
        lon, lat = lon + dlon, lat + dlat
        coords.append((lon, lat))
    return LineString(coords)


def _impact_cone(line: LineString) -> Polygon:
    try:
        return line.buffer(0.25)  # ~25 km lateral uncertainty
    except Exception:  # noqa: BLE001
        return line.buffer(0.0)


def _landing_probability(cone: Polygon, sector: Polygon, horizon_hours: int) -> float:
    if cone.is_empty or sector.is_empty:
        return 0.0
    inter = cone.intersection(sector)
    if inter.is_empty:
        return 0.0
    eta_factor = max(0.2, 1.0 - (horizon_hours / 168.0))
    overlap = inter.area / cone.area if cone.area > 0 else 0.0
    return min(99.0, round(overlap * 100 * eta_factor, 1))


def _h2s_flag(density_level: str, density_score: float, wind_kts: Optional[float]) -> Optional[str]:
    w = wind_kts if wind_kts is not None else 0.0
    if density_level == "high" and density_score >= 0.7 and w < 5.0:
        return "alerte_gaz"
    if density_level in ("high", "medium") and w < 5.0:
        return "attention_gaz"
    return None


def normalize_drift_predictions(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for f in features:
        props = f.get("properties", {})
        if not props.get("external_id"):
            props["external_id"] = common.external_id(
                "drift", props.get("feature_type"), props.get("origin_lon"),
                props.get("origin_lat"), props.get("prediction_horizon_days"),
                props.get("target_sector"),
            )
        out.append(f)
    return out
