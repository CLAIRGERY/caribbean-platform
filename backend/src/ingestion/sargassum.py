"""Sargassum observation collector.

Source: Copernicus Data Space Ecosystem (CDSE) Sentinel-2 L2A STAC catalog.
- Anonymous STAC search works without credentials.
- Band streaming + FAI computation requires OAuth2 credentials
  (CDSE_USERNAME / CDSE_PASSWORD).

The Floating Algae Index (FAI) computation and false-positive ML filter are
reused from ``sakgaze/src/pipeline.py``. When credentials are absent the
collector returns an empty result and logs a clear warning — it NEVER
substitutes synthetic/demo data in production.
"""
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.src.ingestion import common

# CDSE endpoints (environment-overridable)
CDSE_STAC_URL = os.getenv(
    "CDSE_STAC_URL", "https://catalogue.dataspace.copernicus.eu/stac"
)
CDSE_AUTH_URL = os.getenv(
    "CDSE_AUTH_URL",
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
)
CDSE_CLIENT_ID = os.getenv("CDSE_CLIENT_ID", "cdse-public")
CDSE_USERNAME = os.getenv("CDSE_USERNAME", "")
CDSE_PASSWORD = os.getenv("CDSE_PASSWORD", "")
CDSE_S3_ACCESS_KEY = os.getenv("CDSE_S3_ACCESS_KEY", "")
CDSE_S3_SECRET_KEY = os.getenv("CDSE_S3_SECRET_KEY", "")

# AOI: Caribbean Basin & Lesser Antilles
AOI_BBOX = (-89.0, 7.0, -59.0, 27.0)
MAX_CLOUD_COVER = float(os.getenv("S2_MAX_CLOUD_COVER", "20"))
COLLECTION = os.getenv("S2_COLLECTION", "sentinel-2-l2a")
LOOKBACK_DAYS = int(os.getenv("SARGASSUM_LOOKBACK_DAYS", "30"))


def fetch_sargassum_detections() -> List[Dict[str, Any]]:
    """Fetch recent Sentinel-2 scenes and derive sargassum polygons.

    Returns a list of GeoJSON features (possibly empty) with the application's
    expected properties: surface_km2, density_score, density_level,
    acquisition_date, source_satellite.
    """
    logger = common.logger
    logger.info("[SARGASSUM] Searching CDSE Sentinel-2 L2A (collection=%s)", COLLECTION)

    items = _search_scenes()
    logger.info("[SARGASSUM] %d candidate scenes", len(items))
    items = _filter_cloud(items)

    if not items:
        logger.warning("[SARGASSUM] No low-cloud scenes found in the AOI window.")
        return []

    if not (CDSE_USERNAME and CDSE_PASSWORD):
        logger.warning(
            "[SARGASSUM] CDSE credentials not configured — cannot stream bands "
            "or compute FAI. Returning empty result (no synthetic fallback)."
        )
        return []

    if not (CDSE_S3_ACCESS_KEY and CDSE_S3_SECRET_KEY):
        logger.warning(
            "[SARGASSUM] CDSE S3 credentials (CDSE_S3_ACCESS_KEY/"
            "CDSE_S3_SECRET_KEY) not configured — cannot stream s3:// band "
            "assets. Returning empty result (no synthetic fallback)."
        )
        return []

    # Full FAI pipeline on the newest low-cloud scene.
    features = _process_scene(items[0])
    logger.info("[SARGASSUM] Vectorized %d detection polygons", len(features))
    return features


def _search_scenes() -> List[Dict[str, Any]]:
    end = datetime.now(timezone.utc)
    start = end - __import__("datetime").timedelta(days=LOOKBACK_DAYS)
    bbox = ",".join(map(str, AOI_BBOX))
    data = common.fetch_json(
        f"{CDSE_STAC_URL}/search",
        params={
            "collections": COLLECTION,
            "bbox": bbox,
            "datetime": f"{start.isoformat()}/{end.isoformat()}",
            "limit": 20,
        },
    )
    return data.get("features", []) if isinstance(data, dict) else []


def _filter_cloud(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    valid = []
    for it in items:
        props = it.get("properties", {})
        cc = props.get("eo:cloud_cover", props.get("cloud_cover", 100.0))
        try:
            cc = float(cc)
        except (TypeError, ValueError):
            cc = 100.0
        if cc <= MAX_CLOUD_COVER:
            valid.append(it)
    valid.sort(key=lambda x: x.get("properties", {}).get("datetime", ""), reverse=True)
    return valid


def _get_band_url(item: Dict[str, Any], band: str) -> Optional[str]:
    assets = item.get("assets", {})
    for key in (f"{band}_10m", f"{band}_20m", f"{band}_60m", band):
        if key in assets and "href" in assets[key]:
            return assets[key]["href"]
    for key, asset in assets.items():
        if band.lower() in key.lower() and "href" in asset:
            return asset["href"]
    return None


def _process_scene(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Stream B04/B08/B11, compute FAI, filter, vectorize. Reuses pipeline logic."""
    try:
        from sakgaze.src.pipeline import (
            compute_fai,
            get_cdse_token,
            ml_false_positive_filter,
            read_band_window,
            vectorize_mask,
        )
    except Exception as exc:  # noqa: BLE001
        common.logger.warning("[SARGASSUM] Could not import FAI pipeline: %s", exc)
        return []

    import numpy as np

    token = ""
    try:
        token = get_cdse_token()
    except Exception as exc:  # noqa: BLE001
        common.logger.warning("[SARGASSUM] CDSE authentication failed: %s", exc)
        return []

    bbox = AOI_BBOX
    red_url = _get_band_url(item, "B04")
    nir_url = _get_band_url(item, "B08")
    swir_url = _get_band_url(item, "B11")
    if not all([red_url, nir_url, swir_url]):
        common.logger.warning("[SARGASSUM] Missing band assets for scene %s", item.get("id"))
        return []

    try:
        red, profile = read_band_window(red_url, bbox, token)
        nir, _ = read_band_window(nir_url, bbox, token)
        swir, _ = read_band_window(swir_url, bbox, token)
    except Exception as exc:  # noqa: BLE001
        common.logger.warning("[SARGASSUM] Band streaming failed: %s", exc)
        return []

    red = red.astype(float) * 1e-4
    nir = nir.astype(float) * 1e-4
    swir = swir.astype(float) * 1e-4

    fai = compute_fai(red, nir, swir)
    candidates = fai > float(os.getenv("FAI_THRESHOLD", "0.008"))
    ml_mask = ml_false_positive_filter(fai, red, nir, swir)
    final_mask = candidates & ml_mask

    acquisition = item["properties"].get("datetime", common.now_iso())
    if isinstance(acquisition, str):
        try:
            acquisition = datetime.fromisoformat(acquisition.replace("Z", "+00:00"))
        except ValueError:
            acquisition = datetime.now(timezone.utc)

    return vectorize_mask(np.asarray(final_mask), profile, acquisition)


def normalize_sargassum_detections(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure each feature carries the application contract + a stable external_id."""
    out = []
    for f in features:
        props = f.get("properties", {})
        acq = props.get("acquisition_date")
        fid = common.external_id(
            "sargassum",
            acq,
            props.get("surface_km2"),
            props.get("density_score"),
            f.get("geometry", {}).get("coordinates"),
        )
        props["external_id"] = fid
        props.setdefault("source_satellite", "S2")
        props.setdefault("source", "cdse_sentinel2")
        out.append({"type": "Feature", "geometry": f.get("geometry"), "properties": props})
    return out
