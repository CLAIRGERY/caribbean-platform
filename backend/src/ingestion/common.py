"""Shared helpers for the ingestion collectors.

Provides:
- a configured httpx client (timeouts, User-Agent, retry with backoff)
- stable external-id hashing for idempotency
- structured logging
- GeoJSON validation
"""
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

# ---------------------------------------------------------------------------
# Configuration (environment-driven, no secrets)
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT = float(os.getenv("INGESTION_REQUEST_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("INGESTION_MAX_RETRIES", "3"))
BACKOFF_BASE = float(os.getenv("INGESTION_BACKOFF_BASE", "2.0"))
USER_AGENT = os.getenv(
    "INGESTION_USER_AGENT",
    "SaKgaZe-Ingestion/1.0 (+https://sakgaze.com)",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("sakgaze.ingestion")


# ---------------------------------------------------------------------------
# HTTP client with retry + backoff
# ---------------------------------------------------------------------------
def get_client() -> httpx.Client:
    client = httpx.Client(
        timeout=httpx.Timeout(REQUEST_TIMEOUT),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, application/geo+json",
        },
    )
    return client


def fetch_json(url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """GET JSON with retry/backoff. Raises on persistent failure."""
    client = get_client()
    last_exc: Optional[Exception] = None
    try:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # noqa: BLE001 - deliberate broad retry
                last_exc = exc
                if attempt == MAX_RETRIES:
                    break
                wait = BACKOFF_BASE ** attempt
                logger.warning(
                    "GET %s attempt %d/%d failed (%s); retrying in %.1fs",
                    url, attempt, MAX_RETRIES, exc, wait,
                )
                time.sleep(wait)
    finally:
        client.close()
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Idempotency: stable external id
# ---------------------------------------------------------------------------
def external_id(source: str, *parts: Any) -> str:
    """Deterministic 64-char hex id from a source tag + ordered fields.

    Feeding the same source + field values always yields the same id, so
    re-running ingestion is naturally idempotent at the database layer.
    """
    raw = "|".join([source] + [str(p) for p in parts])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# GeoJSON validation
# ---------------------------------------------------------------------------
def is_valid_feature(f: Dict[str, Any]) -> bool:
    """Return True if a GeoJSON feature has a usable geometry."""
    geom = f.get("geometry")
    if not isinstance(geom, dict):
        return False
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype not in ("Point", "LineString", "Polygon", "MultiPolygon"):
        return False
    if coords is None:
        return False
    return True


def build_feature_collection(
    features: List[Dict[str, Any]],
    source: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    valid = [f for f in features if is_valid_feature(f)]
    props: Dict[str, Any] = {"source": source, "generated_at": now_iso()}
    if extra:
        props.update(extra)
    return {
        "type": "FeatureCollection",
        "features": valid,
        "properties": props,
    }


# ---------------------------------------------------------------------------
# JSON-serializable safe dump (for logging / debugging)
# ---------------------------------------------------------------------------
def safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, default=str)
    except Exception:  # noqa: BLE001
        return str(obj)
