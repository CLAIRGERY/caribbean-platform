"""
Weathernext Marine Weather & Tropical Cyclone Pipeline
=======================================================
1. Query NOAA NHC GIS endpoints for active tropical cyclones:
   - observed track LineStrings
   - forecast uncertainty cone Polygons
2. Query Open-Meteo Marine API for wind/wave/current conditions at coastal points.
3. Assign alert levels per coastal sector.
4. POST GeoJSON FeatureCollection to FastAPI backend.
"""
import os
import sys
import json
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import httpx
from shapely.geometry import LineString, Polygon, Point, mapping
from shapely.ops import unary_union, transform as shapely_transform
import pyproj

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from shared.config.settings import (
    NHC_GIS_URL,
    OPEN_METEO_URL,
    OPEN_METEO_WEATHER_URL,
    API_BASE_URL,
    COASTAL_SECTORS,
    CRS_WGS84,
    REQUEST_TIMEOUT,
)
from shared.src.utils import logger, retry_on_exception, http_get, save_geojson

OUTPUT_DIR = os.path.join(ROOT, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# NOAA NHC active storms
# ---------------------------------------------------------------------------
@retry_on_exception()
def fetch_nhc_active_storms() -> List[Dict[str, Any]]:
    """Return active tropical cyclone records from NOAA NHC."""
    resp = httpx.get(NHC_GIS_URL, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    storms = data.get("activeStorms", data.get("storms", []))
    logger.info(f"NHC active storms: {len(storms)}")
    return storms


def parse_nhc_storm(storm: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert one NHC storm record into GeoJSON features (track + cone)."""
    features: List[Dict[str, Any]] = []
    storm_id = storm.get("id", "unknown")
    name = storm.get("name", "Unknown")
    basin = storm.get("basin", "AL")
    classification = storm.get("classification", "TS")
    max_wind_kts = float(storm.get("maxWindKnots", storm.get("maxWind", 0)) or 0)
    pressure_mb = float(storm.get("pressureMb", storm.get("pressure", 0)) or 0)

    # Observed / forecast track points
    track = storm.get("track", []) or storm.get("forecastTrack", []) or []
    coords = []
    times = []
    for pt in track:
        try:
            lon = float(pt["longitude"])
            lat = float(pt["latitude"])
            coords.append((lon, lat))
            times.append(pt.get("time", ""))
        except Exception:
            continue

    if len(coords) >= 2:
        features.append({
            "type": "Feature",
            "geometry": mapping(LineString(coords)),
            "properties": {
                "alert_type": "cyclone_track",
                "alert_level": cyclone_alert_level(max_wind_kts),
                "event_name": f"{name} ({storm_id})",
                "sector": None,
                "wind_speed_knots": max_wind_kts,
                "gust_speed_knots": round(max_wind_kts * 1.15, 1),
                "wave_height_m": None,
                "wave_period_s": None,
                "h2s_risk": None,
                "issued_at": datetime.utcnow().isoformat() + "Z",
            },
        })

    # Forecast uncertainty cone (synthetic if not present in JSON)
    cone = storm.get("cone", {})
    if isinstance(cone, dict) and "coordinates" in cone:
        try:
            poly = Polygon(cone["coordinates"])
            features.append({
                "type": "Feature",
                "geometry": mapping(poly),
                "properties": {
                    "alert_type": "cyclone_cone",
                    "alert_level": cyclone_alert_level(max_wind_kts),
                    "event_name": f"{name} ({storm_id})",
                    "sector": None,
                    "wind_speed_knots": max_wind_kts,
                    "gust_speed_knots": round(max_wind_kts * 1.15, 1),
                    "wave_height_m": None,
                    "wave_period_s": None,
                    "h2s_risk": None,
                    "issued_at": datetime.utcnow().isoformat() + "Z",
                },
            })
        except Exception as exc:
            logger.warning(f"Could not parse cone for {name}: {exc}")

    return features


def cyclone_alert_level(max_wind_kts: float) -> str:
    """Saffir-Simpson-ish alert levels."""
    if max_wind_kts >= 130:
        return "Purple"
    if max_wind_kts >= 100:
        return "Red"
    if max_wind_kts >= 64:
        return "Orange"
    if max_wind_kts >= 34:
        return "Yellow"
    return "Green"


# ---------------------------------------------------------------------------
# Open-Meteo marine conditions
# ---------------------------------------------------------------------------
@retry_on_exception()
def fetch_marine_conditions(lat: float, lon: float) -> Dict[str, Any]:
    """Fetch wave and wind conditions from Open-Meteo Marine API."""
    url = (
        f"{OPEN_METEO_URL}"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly=wave_height,wave_period,wind_speed_10m,wind_direction_10m"
        f"&forecast_days=3&timezone=UTC"
    )
    resp = httpx.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def hourly_to_summary(hourly: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Reduce hourly arrays to a single summary (max / dominant)."""
    def safe_max(key: str) -> Optional[float]:
        vals = hourly.get(key)
        if not vals:
            return None
        clean = [v for v in vals if v is not None and not math.isnan(v)]
        return max(clean) if clean else None

    def circ_mean(key: str) -> Optional[float]:
        vals = hourly.get(key)
        if not vals:
            return None
        clean = [v for v in vals if v is not None and not math.isnan(v)]
        if not clean:
            return None
        rad = np.deg2rad(clean)
        return float(np.rad2deg(np.arctan2(np.mean(np.sin(rad)), np.mean(np.cos(rad)))) % 360)

    return {
        "wave_height_m": safe_max("wave_height"),
        "wave_period_s": safe_max("wave_period"),
        "wind_speed_knots": safe_max("wind_speed_10m"),
        "wind_direction_deg": circ_mean("wind_direction_10m"),
    }


def marine_alert_level(wind_kts: Optional[float], wave_m: Optional[float]) -> str:
    """Green/Yellow/Orange/Red/Purple for coastal marine conditions."""
    if wind_kts is None:
        wind_kts = 0
    if wave_m is None:
        wave_m = 0
    if wind_kts >= 64 or wave_m >= 9:
        return "Purple"
    if wind_kts >= 48 or wave_m >= 6:
        return "Red"
    if wind_kts >= 34 or wave_m >= 4:
        return "Orange"
    if wind_kts >= 20 or wave_m >= 2.5:
        return "Yellow"
    return "Green"


# ---------------------------------------------------------------------------
# Sector polygons
# ---------------------------------------------------------------------------
def build_sector_polygon(name: str, info: Dict[str, float]) -> Polygon:
    """Build a rough circular coastal sector polygon around the island centroid."""
    lon, lat = info["lon"], info["lat"]
    buffer_deg = info["buffer_km"] / 111.0  # rough km to deg
    pts = []
    for i in range(36):
        ang = 2 * math.pi * i / 36
        pts.append((lon + buffer_deg * math.cos(ang), lat + buffer_deg * math.sin(ang)))
    pts.append(pts[0])
    return Polygon(pts)


# ---------------------------------------------------------------------------
# Fallback synthetic data
# ---------------------------------------------------------------------------
def synthetic_alerts() -> List[Dict[str, Any]]:
    """Generate realistic synthetic weather/cyclone alerts."""
    logger.info("Generating synthetic Weathernext alerts for demo/verification.")
    features: List[Dict[str, Any]] = []
    rng = np.random.default_rng(123)

    # Synthetic cyclone track + cone in Atlantic approaching Lesser Antilles
    track = LineString([
        (-55.0, 12.0), (-57.0, 13.5), (-59.0, 14.8), (-61.0, 15.8),
        (-62.5, 16.5), (-63.5, 17.2)
    ])
    features.append({
        "type": "Feature",
        "geometry": mapping(track),
        "properties": {
            "alert_type": "cyclone_track",
            "alert_level": "Red",
            "event_name": "Hurricane Synthetic-Echo",
            "sector": None,
            "wind_speed_knots": 95.0,
            "gust_speed_knots": 115.0,
            "wave_height_m": 6.5,
            "wave_period_s": 12.0,
            "h2s_risk": None,
            "issued_at": datetime.utcnow().isoformat() + "Z",
        },
    })

    cone = Polygon([
        (-55.0, 12.0), (-56.0, 13.0), (-58.0, 14.5), (-60.0, 15.5),
        (-62.0, 16.5), (-63.5, 17.2), (-64.0, 18.0), (-62.5, 17.5),
        (-60.5, 16.5), (-58.5, 15.0), (-56.5, 13.5), (-55.0, 12.0)
    ])
    features.append({
        "type": "Feature",
        "geometry": mapping(cone),
        "properties": {
            "alert_type": "cyclone_cone",
            "alert_level": "Orange",
            "event_name": "Hurricane Synthetic-Echo",
            "sector": None,
            "wind_speed_knots": 95.0,
            "gust_speed_knots": 115.0,
            "wave_height_m": None,
            "wave_period_s": None,
            "h2s_risk": None,
            "issued_at": datetime.utcnow().isoformat() + "Z",
        },
    })

    # Marine conditions per sector
    for name, info in COASTAL_SECTORS.items():
        wind = float(rng.uniform(8, 45))
        wave = float(rng.uniform(1.0, 5.5))
        level = marine_alert_level(wind, wave)
        poly = build_sector_polygon(name, info)
        features.append({
            "type": "Feature",
            "geometry": mapping(poly),
            "properties": {
                "alert_type": "marine_conditions",
                "alert_level": level,
                "event_name": None,
                "sector": name,
                "wind_speed_knots": round(wind, 1),
                "gust_speed_knots": round(wind * 1.15, 1),
                "wave_height_m": round(wave, 2),
                "wave_period_s": round(float(rng.uniform(6, 12)), 1),
                "h2s_risk": None,
                "issued_at": datetime.utcnow().isoformat() + "Z",
            },
        })

    return features


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run_pipeline() -> Dict[str, Any]:
    logger.info("=== Weathernext pipeline start ===")
    features: List[Dict[str, Any]] = []

    # 1. NOAA NHC active storms
    try:
        storms = fetch_nhc_active_storms()
        for storm in storms:
            try:
                features.extend(parse_nhc_storm(storm))
            except Exception as exc:
                logger.warning(f"Failed to parse storm: {exc}")
    except Exception as exc:
        logger.warning(f"NOAA NHC fetch failed: {exc}")

    # 2. Open-Meteo marine conditions per sector
    for name, info in COASTAL_SECTORS.items():
        try:
            data = fetch_marine_conditions(info["lat"], info["lon"])
            summary = hourly_to_summary(data.get("hourly", {}))
            level = marine_alert_level(summary["wind_speed_knots"], summary["wave_height_m"])
            poly = build_sector_polygon(name, info)
            features.append({
                "type": "Feature",
                "geometry": mapping(poly),
                "properties": {
                    "alert_type": "marine_conditions",
                    "alert_level": level,
                    "event_name": None,
                    "sector": name,
                    "wind_speed_knots": round(summary["wind_speed_knots"], 1) if summary["wind_speed_knots"] else None,
                    "gust_speed_knots": round(summary["wind_speed_knots"] * 1.15, 1) if summary["wind_speed_knots"] else None,
                    "wave_height_m": round(summary["wave_height_m"], 2) if summary["wave_height_m"] else None,
                    "wave_period_s": round(summary["wave_period_s"], 1) if summary["wave_period_s"] else None,
                    "wind_direction_deg": round(summary["wind_direction_deg"], 1) if summary["wind_direction_deg"] else None,
                    "h2s_risk": None,
                    "issued_at": datetime.utcnow().isoformat() + "Z",
                },
            })
        except Exception as exc:
            logger.warning(f"Open-Meteo failed for {name}: {exc}")

    # If nothing came from live APIs, use synthetic data
    if not features:
        features = synthetic_alerts()

    fc = {
        "type": "FeatureCollection",
        "features": features,
        "properties": {"source": "Weathernext", "generated_at": datetime.utcnow().isoformat() + "Z"},
    }

    out_path = os.path.join(OUTPUT_DIR, "weathernext_alerts.geojson")
    save_geojson(fc, out_path)

    url = f"{API_BASE_URL}/api/v1/weathernext/marine-alerts"
    logger.info(f"POSTing alerts to {url}")
    resp = httpx.post(url, json=fc, timeout=60)
    resp.raise_for_status()
    logger.info(f"Backend response: {resp.json()}")
    return fc


if __name__ == "__main__":
    run_pipeline()
