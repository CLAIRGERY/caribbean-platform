"""
Shared utilities: retries, HTTP sessions, GeoJSON helpers, geometry ops.
"""
import json
import time
import logging
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

import requests
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from shared.config.settings import (
    MAX_RETRIES,
    BACKOFF_BASE,
    REQUEST_TIMEOUT,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("caribbean_platform")


def retry_on_exception(max_retries: int = MAX_RETRIES, backoff_base: float = BACKOFF_BASE):
    """Exponential backoff retry decorator for any callable."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc: Optional[Exception] = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    wait = backoff_base ** attempt
                    logger.warning(f"{func.__name__} attempt {attempt}/{max_retries} failed: {exc}. Retrying in {wait:.1f}s...")
                    time.sleep(wait)
            raise last_exc
        return wrapper
    return decorator


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "SaKgaZé-Weathernext-Platform/1.0 (Hermes-Agent)",
        "Accept": "application/json",
    })
    session.timeout = REQUEST_TIMEOUT
    return session


@retry_on_exception()
def http_get(session: requests.Session, url: str, **kwargs) -> requests.Response:
    """HTTP GET with retries and configurable params."""
    resp = session.get(url, **kwargs)
    resp.raise_for_status()
    return resp


@retry_on_exception()
def http_post(session: requests.Session, url: str, **kwargs) -> requests.Response:
    """HTTP POST with retries and configurable params."""
    resp = session.post(url, **kwargs)
    resp.raise_for_status()
    return resp


def clean_geojson_feature_collection(features: List[Dict[str, Any]], properties_schema: Optional[Dict] = None) -> Dict[str, Any]:
    """Return a validated GeoJSON FeatureCollection, dropping invalid geometries."""
    valid = []
    for f in features:
        try:
            geom = shape(f.get("geometry", {}))
            if not geom.is_valid:
                geom = geom.buffer(0)
            if geom.is_empty or not geom.is_valid:
                continue
            f["geometry"] = mapping(geom)
            valid.append(f)
        except Exception as exc:
            logger.warning(f"Skipping invalid feature: {exc}")
    return {
        "type": "FeatureCollection",
        "features": valid,
        "properties": properties_schema or {},
    }


def merge_polygons(geoms: List[Any]) -> Any:
    """Merge list of shapely geometries via unary union, fixing invalid ones."""
    cleaned = []
    for g in geoms:
        if not g.is_valid:
            g = g.buffer(0)
        if not g.is_empty:
            cleaned.append(g)
    return unary_union(cleaned)


def save_geojson(data: Dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved GeoJSON: {path}")


def load_geojson(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
