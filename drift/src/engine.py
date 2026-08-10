"""
Coupled Sargassum Drift Engine & Coastal Risk Scoring
=====================================================
1. Load latest sargassum detections and marine weather vectors.
2. Advect sargassum polygon centroids using:
     V_drift = 0.03 * V_wind + 1.0 * V_current
3. Generate 24h, 48h, 72h drift LineStrings and grounding impact Polygons.
4. Compute landing probability per coastal sector.
5. Flag H2S stagnation risk when massive density meets low onshore wind (<5 kts).
6. POST drift predictions to the FastAPI backend.
"""
import os
import sys
import json
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import httpx
from shapely.geometry import LineString, Polygon, Point, mapping, shape
from shapely.ops import unary_union, transform as shapely_transform

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from shared.config.settings import (
    API_BASE_URL,
    COASTAL_SECTORS,
    OPEN_METEO_URL,
    REQUEST_TIMEOUT,
)
from shared.src.utils import logger, retry_on_exception, http_get, save_geojson

OUTPUT_DIR = os.path.join(ROOT, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Earth radius for haversine / velocity displacement
R_EARTH_M = 6_371_000.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def knots_to_ms(knots: float) -> float:
    return knots * 0.514444


def ms_to_knots(ms: float) -> float:
    return ms / 0.514444


def bearing_to_components(speed_ms: float, bearing_deg: float) -> Tuple[float, float]:
    """Return (u, v) velocity components in m/s: u=east, v=north."""
    rad = math.radians(bearing_deg)
    u = speed_ms * math.sin(rad)
    v = speed_ms * math.cos(rad)
    return u, v


def move_point(lon: float, lat: float, u_ms: float, v_ms: float, dt_hours: float) -> Tuple[float, float]:
    """Advect a (lon, lat) point by velocity components for dt_hours."""
    dx = u_ms * dt_hours * 3600.0
    dy = v_ms * dt_hours * 3600.0
    dlat = (dy / R_EARTH_M) * (180.0 / math.pi)
    dlon = (dx / (R_EARTH_M * math.cos(math.radians(lat)))) * (180.0 / math.pi)
    return lon + dlon, lat + dlat


def sector_polygon(name: str, info: Dict[str, float]) -> Polygon:
    """Re-use the same circular sector footprint as Weathernext."""
    lon, lat = info["lon"], info["lat"]
    buffer_deg = info["buffer_km"] / 111.0
    pts = []
    for i in range(36):
        ang = 2 * math.pi * i / 36
        pts.append((lon + buffer_deg * math.cos(ang), lat + buffer_deg * math.sin(ang)))
    pts.append(pts[0])
    return Polygon(pts)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------
@retry_on_exception()
def fetch_latest_detections() -> List[Dict[str, Any]]:
    """Pull the latest sargassum detection GeoJSON from local output."""
    path = os.path.join(OUTPUT_DIR, "sakgaze_detections.geojson")
    if not os.path.exists(path):
        logger.warning("No local detections found; drift engine cannot run.")
        return []
    with open(path, "r", encoding="utf-8") as f:
        fc = json.load(f)
    return fc.get("features", [])


@retry_on_exception()
def fetch_marine_vector(lat: float, lon: float) -> Dict[str, float]:
    """Fetch 10m wind/current vector summary for a point."""
    # Open-Meteo Marine API (ocean currents available in some variants)
    url = (
        f"{OPEN_METEO_URL}"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly=wind_speed_10m,wind_direction_10m,ocean_current_velocity,ocean_current_direction"
        f"&forecast_days=3&timezone=UTC"
    )
    resp = httpx.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    hourly = data.get("hourly", {})

    def mean_or_none(key: str) -> Optional[float]:
        vals = hourly.get(key)
        if not vals:
            return None
        clean = [v for v in vals if v is not None and not math.isnan(v)]
        return sum(clean) / len(clean) if clean else None

    return {
        "wind_speed_knots": mean_or_none("wind_speed_10m") or 0.0,
        "wind_direction_deg": mean_or_none("wind_direction_10m") or 0.0,
        "current_speed_ms": mean_or_none("ocean_current_velocity") or 0.0,
        "current_direction_deg": mean_or_none("ocean_current_direction") or 0.0,
    }


# ---------------------------------------------------------------------------
# Drift physics
# ---------------------------------------------------------------------------
def compute_drift_velocity(marine: Dict[str, float]) -> Tuple[float, float]:
    """
    V_drift = 0.03 * V_wind + 1.0 * V_current
    Returns (u_drift, v_drift) in m/s.
    """
    wind_ms = knots_to_ms(marine["wind_speed_knots"])
    wind_u, wind_v = bearing_to_components(wind_ms, marine["wind_direction_deg"])

    current_ms = marine["current_speed_ms"]
    current_u, current_v = bearing_to_components(current_ms, marine["current_direction_deg"])

    u_drift = 0.03 * wind_u + 1.0 * current_u
    v_drift = 0.03 * wind_v + 1.0 * current_v
    return u_drift, v_drift


def advect_centroid(lon: float, lat: float, u: float, v: float, horizon_hours: int) -> LineString:
    """Build a drift LineString over fixed hourly steps."""
    coords = [(lon, lat)]
    for h in range(1, horizon_hours + 1):
        lon, lat = move_point(lon, lat, u, v, 1.0)
        coords.append((lon, lat))
    return LineString(coords)


def build_impact_cone(line: LineString) -> Polygon:
    """Create a buffer polygon around the drift line to represent landing uncertainty."""
    # Use a geodesic-aware approximate buffer by transforming to a local metric CRS.
    from pyproj import Transformer, CRS
    centroid = line.centroid
    lat = centroid.y
    # UTM zone
    zone = int((centroid.x + 180) / 6) + 1
    epsg = 32600 + zone if lat >= 0 else 32700 + zone
    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    back = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    metric_line = shapely_transform(transformer.transform, line)
    cone = metric_line.buffer(5000)  # 5 km lateral uncertainty
    return shapely_transform(back.transform, cone)


# ---------------------------------------------------------------------------
# Risk scoring
# ---------------------------------------------------------------------------
def landing_probability(drift_geom: Any, sector_geom: Polygon, horizon_hours: int) -> float:
    """Simple geometric overlap-based probability."""
    if not drift_geom.is_valid:
        drift_geom = drift_geom.buffer(0)
    if not sector_geom.is_valid:
        sector_geom = sector_geom.buffer(0)
    inter = drift_geom.intersection(sector_geom)
    if inter.is_empty:
        return 0.0
    # Scale by horizon: closer ETA = higher prob
    eta_factor = max(0.2, 1.0 - (horizon_hours / 168.0))
    overlap_ratio = inter.area / drift_geom.area if drift_geom.area > 0 else 0.0
    return min(99.0, round(overlap_ratio * 100 * eta_factor, 1))


def h2s_risk_flag(density_level: str, density_score: float, wind_knots: float) -> Optional[str]:
    """Flag H2S stagnation risk for massive accumulation with low onshore wind."""
    if density_level == "high" and density_score >= 0.7 and wind_knots < 5.0:
        return "alerte_gaz"
    if density_level in ("high", "medium") and wind_knots < 5.0:
        return "attention_gaz"
    return None


# ---------------------------------------------------------------------------
# Fallback synthetic drift
# ---------------------------------------------------------------------------
def synthetic_drift(detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate deterministic drift trajectories when live vectors are unavailable."""
    logger.info("Generating synthetic drift predictions.")
    features: List[Dict[str, Any]] = []
    rng = np.random.default_rng(2024)

    for det in detections:
        props = det.get("properties", {})
        geom = shape(det["geometry"])
        centroid = geom.centroid
        lon0, lat0 = centroid.x, centroid.y

        # Synthetic drift toward WNW at ~0.4 m/s
        u = -0.25 + rng.uniform(-0.1, 0.1)  # east-west
        v = 0.30 + rng.uniform(-0.1, 0.1)   # north-south

        for horizon in [24, 48, 72]:
            line = advect_centroid(lon0, lat0, u, v, horizon)
            cone = build_impact_cone(line)
            for sector_name, info in COASTAL_SECTORS.items():
                sec = sector_polygon(sector_name, info)
                prob = landing_probability(cone, sec, horizon)
                if prob <= 0:
                    continue
                h2s = h2s_risk_flag(
                    props.get("density_level", "low"),
                    props.get("density_score", 0.0),
                    rng.uniform(3, 8),
                )
                features.append({
                    "type": "Feature",
                    "geometry": mapping(cone),
                    "properties": {
                        "prediction_horizon_days": horizon // 24,
                        "eta_hours": horizon,
                        "landing_probability_pct": prob,
                        "target_sector": sector_name,
                        "origin_lon": round(lon0, 5),
                        "origin_lat": round(lat0, 5),
                        "source_density_level": props.get("density_level"),
                        "source_surface_km2": props.get("surface_km2"),
                        "h2s_risk": h2s,
                        "generated_at": datetime.utcnow().isoformat() + "Z",
                    },
                })
            # Also emit the trajectory line
            features.append({
                "type": "Feature",
                "geometry": mapping(line),
                "properties": {
                    "prediction_horizon_days": horizon // 24,
                    "eta_hours": horizon,
                    "landing_probability_pct": 0.0,
                    "target_sector": "trajectory",
                    "origin_lon": round(lon0, 5),
                    "origin_lat": round(lat0, 5),
                    "feature_type": "drift_line",
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                },
            })
    return features


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------
def run_engine() -> Dict[str, Any]:
    logger.info("=== Coupled drift engine start ===")
    detections = fetch_latest_detections()
    if not detections:
        logger.error("No detections available. Run sakgaze pipeline first.")
        return {"type": "FeatureCollection", "features": []}

    features: List[Dict[str, Any]] = []
    live_vectors_ok = True

    for det in detections:
        props = det.get("properties", {})
        geom = shape(det["geometry"])
        centroid = geom.centroid
        lon0, lat0 = centroid.x, centroid.y

        try:
            marine = fetch_marine_vector(lat0, lon0)
            u, v = compute_drift_velocity(marine)
        except Exception as exc:
            logger.warning(f"Could not fetch marine vector for centroid ({lon0}, {lat0}): {exc}")
            live_vectors_ok = False
            # deterministic fallback vector
            u, v = -0.25, 0.30

        for horizon in [24, 48, 72]:
            line = advect_centroid(lon0, lat0, u, v, horizon)
            cone = build_impact_cone(line)
            for sector_name, info in COASTAL_SECTORS.items():
                sec = sector_polygon(sector_name, info)
                prob = landing_probability(cone, sec, horizon)
                if prob <= 0:
                    continue
                h2s = h2s_risk_flag(
                    props.get("density_level", "low"),
                    props.get("density_score", 0.0),
                    marine.get("wind_speed_knots", 0.0) if live_vectors_ok else 4.0,
                )
                features.append({
                    "type": "Feature",
                    "geometry": mapping(cone),
                    "properties": {
                        "prediction_horizon_days": horizon // 24,
                        "eta_hours": horizon,
                        "landing_probability_pct": prob,
                        "target_sector": sector_name,
                        "origin_lon": round(lon0, 5),
                        "origin_lat": round(lat0, 5),
                        "source_density_level": props.get("density_level"),
                        "source_surface_km2": props.get("surface_km2"),
                        "h2s_risk": h2s,
                        "generated_at": datetime.utcnow().isoformat() + "Z",
                    },
                })
            features.append({
                "type": "Feature",
                "geometry": mapping(line),
                "properties": {
                    "prediction_horizon_days": horizon // 24,
                    "eta_hours": horizon,
                    "landing_probability_pct": 0.0,
                    "target_sector": "trajectory",
                    "origin_lon": round(lon0, 5),
                    "origin_lat": round(lat0, 5),
                    "feature_type": "drift_line",
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                },
            })

    fc = {
        "type": "FeatureCollection",
        "features": features,
        "properties": {"source": "drift_engine", "generated_at": datetime.utcnow().isoformat() + "Z"},
    }

    out_path = os.path.join(OUTPUT_DIR, "drift_predictions.geojson")
    save_geojson(fc, out_path)

    url = f"{API_BASE_URL}/api/v1/sakgaze/drift-predictions"
    logger.info(f"POSTing drift predictions to {url}")
    resp = httpx.post(url, json=fc, timeout=60)
    resp.raise_for_status()
    logger.info(f"Backend response: {resp.json()}")
    return fc


if __name__ == "__main__":
    run_engine()
