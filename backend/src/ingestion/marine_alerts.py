"""Marine alerts collector.

Sources (both public, no credentials required):
- NOAA National Hurricane Center ``CurrentStorms.json`` for active tropical
  cyclone tracks and forecast uncertainty cones.
- Open-Meteo Marine API for wave/current conditions, and Open-Meteo Forecast
  API for 10m wind (the Marine API does NOT expose wind — that is a known gap).

The /api/v1/weathernext/ route is retained for backward compatibility with the
frontend, but the data behind it is NOAA + Open-Meteo (NOT Google WeatherNext,
which has no public production API).
"""
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shapely.geometry import LineString, Polygon, mapping

from backend.src.ingestion import common

NHC_STORMS_URL = os.getenv(
    "NHC_STORMS_URL", "https://www.nhc.noaa.gov/CurrentStorms.json"
)
OPEN_METEO_MARINE_URL = os.getenv(
    "OPEN_METEO_MARINE_URL", "https://marine-api.open-meteo.com/v1/marine"
)
OPEN_METEO_FORECAST_URL = os.getenv(
    "OPEN_METEO_FORECAST_URL", "https://api.open-meteo.com/v1/forecast"
)

# Coastal sectors (name, centroid lon/lat, buffer km)
COASTAL_SECTORS = {
    "Guadeloupe": {"lon": -61.55, "lat": 16.27, "buffer_km": 25.0},
    "Martinique": {"lon": -61.02, "lat": 14.64, "buffer_km": 25.0},
    "St. Martin": {"lon": -63.05, "lat": 18.07, "buffer_km": 20.0},
    "St. Barths": {"lon": -62.83, "lat": 17.90, "buffer_km": 15.0},
    "Dominica": {"lon": -61.37, "lat": 15.41, "buffer_km": 20.0},
    "St. Lucia": {"lon": -60.98, "lat": 13.91, "buffer_km": 20.0},
    "Barbados": {"lon": -59.54, "lat": 13.19, "buffer_km": 20.0},
    "Grenada": {"lon": -61.72, "lat": 12.12, "buffer_km": 20.0},
}


def fetch_marine_alerts() -> List[Dict[str, Any]]:
    """Return coastal marine-alert features from NOAA + Open-Meteo."""
    features: List[Dict[str, Any]] = []

    # 1. Active tropical cyclones (NOAA NHC)
    features.extend(_fetch_cyclones())

    # 2. Per-sector marine conditions (Open-Meteo)
    features.extend(_fetch_coastal_conditions())

    return features


def _fetch_cyclones() -> List[Dict[str, Any]]:
    logger = common.logger
    features: List[Dict[str, Any]] = []
    try:
        data = common.fetch_json(NHC_STORMS_URL)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[MARINE] NOAA NHC fetch failed: %s", exc)
        return features

    storms = data.get("activeStorms", []) if isinstance(data, dict) else []
    logger.info("[MARINE] %d active storm(s) from NOAA NHC", len(storms))

    for storm in storms:
        name = storm.get("name", "Unknown")
        storm_id = storm.get("id", "unknown")
        basin = storm.get("binNumber", storm.get("basin", ""))
        max_wind = float(storm.get("intensity", 0) or 0)  # knots
        lat = storm.get("latitudeNumeric")
        lon = storm.get("longitudeNumeric")

        level = _cyclone_level(max_wind)

        # Forecast track as a LineString (forecast points if present, else current pos)
        coords = []
        fpoints = storm.get("forecast", []) or storm.get("track", [])
        for pt in fpoints:
            try:
                coords.append((float(pt["longitudeNumeric"]), float(pt["latitudeNumeric"])))
            except (KeyError, TypeError, ValueError):
                continue
        if lat is not None and lon is not None:
            coords.insert(0, (float(lon), float(lat)))
        coords = [(c[0], c[1]) for c in coords if c[0] is not None and c[1] is not None]

        issued = storm.get("lastUpdate") or common.now_iso()

        if len(coords) >= 2:
            fid = common.external_id("marine", "cyclone_track", storm_id, issued)
            features.append({
                "type": "Feature",
                "geometry": mapping(LineString(coords)),
                "properties": {
                    "alert_type": "cyclone_track",
                    "alert_level": level,
                    "event_name": f"{name} ({basin or storm_id})",
                    "sector": None,
                    "wind_speed_knots": max_wind or None,
                    "gust_speed_knots": round(max_wind * 1.15, 1) if max_wind else None,
                    "wave_height_m": None,
                    "wave_period_s": None,
                    "h2s_risk": None,
                    "issued_at": issued,
                    "source": "noaa_nhc",
                    "external_id": fid,
                },
            })

        # Uncertainty cone (buffer around current position → forecast)
        if lat is not None and lon is not None and len(coords) >= 2:
            cone = _uncertainty_cone(coords)
            if cone is not None:
                fid = common.external_id("marine", "cyclone_cone", storm_id, issued)
                features.append({
                    "type": "Feature",
                    "geometry": mapping(cone),
                    "properties": {
                        "alert_type": "cyclone_cone",
                        "alert_level": level,
                        "event_name": f"{name} ({basin or storm_id})",
                        "sector": None,
                        "wind_speed_knots": max_wind or None,
                        "gust_speed_knots": round(max_wind * 1.15, 1) if max_wind else None,
                        "wave_height_m": None,
                        "wave_period_s": None,
                        "h2s_risk": None,
                        "issued_at": issued,
                        "source": "noaa_nhc",
                        "external_id": fid,
                    },
                })
    return features


def _uncertainty_cone(coords: List[Any]) -> Optional[Polygon]:
    line = LineString(coords)
    try:
        return line.buffer(0.5)  # ~50 km lateral uncertainty cone
    except Exception:  # noqa: BLE001
        return None


def _cyclone_level(max_wind_kts: float) -> str:
    if max_wind_kts >= 130:
        return "Purple"
    if max_wind_kts >= 100:
        return "Red"
    if max_wind_kts >= 64:
        return "Orange"
    if max_wind_kts >= 34:
        return "Yellow"
    return "Green"


def _fetch_coastal_conditions() -> List[Dict[str, Any]]:
    logger = common.logger
    features: List[Dict[str, Any]] = []
    for name, info in COASTAL_SECTORS.items():
        try:
            marine = _fetch_marine_summary(info["lat"], info["lon"])
            wind = _fetch_wind_summary(info["lat"], info["lon"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("[MARINE] Open-Meteo failed for %s: %s", name, exc)
            continue

        wind_kts = wind.get("wind_speed_knots")
        gust_kts = wind.get("gust_speed_knots")
        wave_m = marine.get("wave_height_m")
        wave_s = marine.get("wave_period_s")
        level = _marine_level(wind_kts, wave_m)

        poly = _sector_polygon(info)
        issued = common.now_iso()
        fid = common.external_id("marine", "coastal", name, issued[:13])  # hourly bucket
        features.append({
            "type": "Feature",
            "geometry": mapping(poly),
            "properties": {
                "alert_type": "marine_conditions",
                "alert_level": level,
                "event_name": None,
                "sector": name,
                "wind_speed_knots": round(wind_kts, 1) if wind_kts else None,
                "gust_speed_knots": round(gust_kts, 1) if gust_kts else None,
                "wave_height_m": round(wave_m, 2) if wave_m else None,
                "wave_period_s": round(wave_s, 1) if wave_s else None,
                "h2s_risk": None,
                "issued_at": issued,
                "source": "open_meteo",
                "external_id": fid,
            },
        })
    return features


def _fetch_marine_summary(lat: float, lon: float) -> Dict[str, Optional[float]]:
    data = common.fetch_json(
        OPEN_METEO_MARINE_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "wave_height,wave_period,ocean_current_velocity,ocean_current_direction",
            "forecast_days": 3,
            "timezone": "UTC",
        },
    )
    hourly = data.get("hourly", {})
    return {
        "wave_height_m": _max(hourly.get("wave_height")),
        "wave_period_s": _max(hourly.get("wave_period")),
        "current_speed_kmh": _mean(hourly.get("ocean_current_velocity")),
        "current_direction_deg": _mean(hourly.get("ocean_current_direction")),
    }


def _fetch_wind_summary(lat: float, lon: float) -> Dict[str, Optional[float]]:
    data = common.fetch_json(
        OPEN_METEO_FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "wind_speed_10m,wind_gusts_10m,wind_direction_10m",
            "forecast_days": 3,
            "timezone": "UTC",
        },
    )
    hourly = data.get("hourly", {})
    speed_kmh = _max(hourly.get("wind_speed_10m"))
    gust_kmh = _max(hourly.get("wind_gusts_10m"))
    # Open-Meteo returns km/h → convert to knots
    return {
        "wind_speed_knots": speed_kmh * 0.539957 if speed_kmh else None,
        "gust_speed_knots": gust_kmh * 0.539957 if gust_kmh else None,
        "wind_direction_deg": _mean(hourly.get("wind_direction_10m")),
    }


def _marine_level(wind_kts: Optional[float], wave_m: Optional[float]) -> str:
    w = wind_kts or 0.0
    h = wave_m or 0.0
    if w >= 64 or h >= 9:
        return "Purple"
    if w >= 48 or h >= 6:
        return "Red"
    if w >= 34 or h >= 4:
        return "Orange"
    if w >= 20 or h >= 2.5:
        return "Yellow"
    return "Green"


def _sector_polygon(info: Dict[str, float]) -> Polygon:
    lon, lat = info["lon"], info["lat"]
    buffer_deg = info["buffer_km"] / 111.0
    pts = []
    for i in range(36):
        ang = 2 * math.pi * i / 36
        pts.append((lon + buffer_deg * math.cos(ang), lat + buffer_deg * math.sin(ang)))
    pts.append(pts[0])
    return Polygon(pts)


def _max(vals: Optional[List[float]]) -> Optional[float]:
    if not vals:
        return None
    clean = [v for v in vals if v is not None and not (isinstance(v, float) and math.isnan(v))]
    return max(clean) if clean else None


def _mean(vals: Optional[List[float]]) -> Optional[float]:
    if not vals:
        return None
    clean = [v for v in vals if v is not None and not (isinstance(v, float) and math.isnan(v))]
    return sum(clean) / len(clean) if clean else None


def normalize_marine_alerts(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate features and ensure stable external_id is present."""
    out = []
    for f in features:
        props = f.get("properties", {})
        if not props.get("external_id"):
            props["external_id"] = common.external_id(
                "marine", props.get("alert_type"), props.get("event_name"),
                props.get("sector"), props.get("issued_at"),
            )
        out.append(f)
    return out
