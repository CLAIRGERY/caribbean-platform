"""API v2 routes (+ v1 compatibility aliases).

Canonical (documented) surface:
    GET /health
    GET /api/v2/status
    GET /api/v2/sargassum
    GET /api/v2/drift
    GET /api/v2/marine-alerts

Compatibility aliases let the current frontend switch over by changing only
``VITE_API_BASE_URL`` to ``https://<new-host>/api/v1``:
    GET /api/v1/sakgaze/detections/latest
    GET /api/v1/sakgaze/drift-predictions/latest
    GET /api/v1/weathernext/marine-alerts/latest
    GET /api/v1/ingestion/status
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import log_event
from app.database.session import get_optional_session, get_session
from app.repositories.geospatial import GeospatialRepository
from app.schemas.params import build_layer_query
from app.services.status import StatusService

API_VERSION = "2.0.0"

router = APIRouter()
compat = APIRouter()

DEFAULT_LIMITS = {"sargassum": 1000, "drift": 1500, "alerts": 500}


def get_repository(request: Request) -> GeospatialRepository:
    return request.app.state.repository


def get_status_service(request: Request) -> StatusService:
    return request.app.state.status_service


def _geojson(payload: Dict[str, Any]) -> Response:
    body = json.dumps(payload, separators=(",", ":"), default=str)
    return Response(
        content=body,
        media_type="application/geo+json",
        headers={
            "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
            "X-Sakgaze-Simplified": "true" if payload.get("meta", {}).get("simplified") else "false",
        },
    )


def _layer_response(
    request: Request,
    session: Session,
    layer_key: str,
    *,
    days: Optional[int],
    limit: Optional[int],
    offset: Optional[int],
    bbox: Optional[str],
    until: Optional[str],
) -> Response:
    query = build_layer_query(
        days=days,
        limit=limit,
        offset=offset,
        bbox=bbox,
        until=until,
        max_limit=settings.max_limit[layer_key],
        default_limit=DEFAULT_LIMITS[layer_key],
        max_days=settings.max_days,
    )
    repository = get_repository(request)
    payload = repository.fetch_layer(session, layer_key, query)
    log_event("layer_fetch", layer=layer_key, count=payload["meta"]["count"],
              days=query.days, limit=query.limit, bbox=bool(query.bbox))
    return _geojson(payload)


def _status_payload(request: Request, session: Optional[Session]) -> Dict[str, Any]:
    service: StatusService = get_status_service(request)
    return service.build(session, api_version=API_VERSION, environment=settings.environment)


# ---------------------------------------------------------------------------
# v2 canonical
# ---------------------------------------------------------------------------
@router.get("/status", summary="Scientific freshness + ingestion ledger")
def status(request: Request,
           session: Optional[Session] = Depends(get_optional_session)) -> Dict[str, Any]:
    return _status_payload(request, session)


@router.get("/sargassum", summary="Sargassum detections (GeoJSON)")
def sargassum(
    request: Request,
    days: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    bbox: Optional[str] = None,
    until: Optional[str] = None,
    session: Session = Depends(get_session),
) -> Response:
    return _layer_response(request, session, "sargassum",
                           days=days, limit=limit, offset=offset, bbox=bbox, until=until)


@router.get("/drift", summary="Drift forecast corridors (GeoJSON)")
def drift(
    request: Request,
    days: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    bbox: Optional[str] = None,
    until: Optional[str] = None,
    session: Session = Depends(get_session),
) -> Response:
    return _layer_response(request, session, "drift",
                           days=days, limit=limit, offset=offset, bbox=bbox, until=until)


@router.get("/marine-alerts", summary="Marine / coastal alerts (GeoJSON)")
def marine_alerts(
    request: Request,
    days: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    bbox: Optional[str] = None,
    until: Optional[str] = None,
    session: Session = Depends(get_session),
) -> Response:
    return _layer_response(request, session, "alerts",
                           days=days, limit=limit, offset=offset, bbox=bbox, until=until)


# ---------------------------------------------------------------------------
# v1 compatibility aliases
# ---------------------------------------------------------------------------
@compat.get("/sakgaze/detections/latest")
def v1_sargassum(
    request: Request,
    days: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    bbox: Optional[str] = None,
    until: Optional[str] = None,
    session: Session = Depends(get_session),
) -> Response:
    return _layer_response(request, session, "sargassum",
                           days=days, limit=limit, offset=offset, bbox=bbox, until=until)


@compat.get("/sakgaze/drift-predictions/latest")
def v1_drift(
    request: Request,
    days: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    bbox: Optional[str] = None,
    until: Optional[str] = None,
    session: Session = Depends(get_session),
) -> Response:
    return _layer_response(request, session, "drift",
                           days=days, limit=limit, offset=offset, bbox=bbox, until=until)


@compat.get("/weathernext/marine-alerts/latest")
def v1_alerts(
    request: Request,
    days: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    bbox: Optional[str] = None,
    until: Optional[str] = None,
    session: Session = Depends(get_session),
) -> Response:
    return _layer_response(request, session, "alerts",
                           days=days, limit=limit, offset=offset, bbox=bbox, until=until)


@compat.get("/ingestion/status")
def v1_status(request: Request,
              session: Optional[Session] = Depends(get_optional_session)) -> Dict[str, Any]:
    return _status_payload(request, session)
