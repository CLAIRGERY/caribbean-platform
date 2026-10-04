"""
FastAPI backend for SaKgaZé ingestion and map read APIs.
"""

import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy.orm import Session

from backend.src.database import init_db, get_db
from backend.src.schemas import GeoJSONFeatureCollection, IngestResponse
from backend.src.crud import (
    ingest_sargassum_detections,
    ingest_drift_predictions,
    ingest_marine_alerts,
    get_latest_sargassum,
    get_latest_marine_alerts,
    get_latest_drift_predictions,
    get_ingestion_status,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="SaKgaZé — Prévision Sargasses Caraïbes",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

default_origins = [
    "https://sakgaze.com",
    "https://www.sakgaze.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://*.onrender.com",
]

cors_env = os.getenv("CORS_ORIGINS", "")

if cors_env:
    origins = [
        origin.strip().rstrip("/")
        for origin in cors_env.split(",")
        if origin.strip()
    ]
else:
    origins = default_origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=["*"],
)

# Compress GeoJSON responses (they gzip ~10x, easing Render free-tier bandwidth).
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> Dict[str, Any]:
    """Process liveness — NEVER depends on the DB (Render probes this on boot)."""
    return {"status": "ok", "service": "sakgaze-api"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Optional DB health; bounded by the engine-level statement timeout."""
    from sqlalchemy import text
    try:
        db.execute(text("SELECT 1"))
        return {"database": "ok"}
    except Exception:
        return {"database": "error"}


@app.get("/api/v1/ingestion/status")
def ingestion_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Read-only ingestion status for the three collectors."""
    try:
        return get_ingestion_status(db)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc.__class__.__name__}")


# ---------------------------------------------------------------------------
# Ingestion endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/sakgaze/detections",
    response_model=IngestResponse,
)
def post_detections(
    fc: GeoJSONFeatureCollection,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ingest_sargassum_detections(
        db,
        fc.model_dump(),
    )


@app.post(
    "/api/v1/sakgaze/drift-predictions",
    response_model=IngestResponse,
)
def post_drift(
    fc: GeoJSONFeatureCollection,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ingest_drift_predictions(
        db,
        fc.model_dump(),
    )


@app.post(
    "/api/v1/weathernext/marine-alerts",
    response_model=IngestResponse,
)
def post_alerts(
    fc: GeoJSONFeatureCollection,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ingest_marine_alerts(
        db,
        fc.model_dump(),
    )


# ---------------------------------------------------------------------------
# Map read endpoints
# ---------------------------------------------------------------------------

@app.get("/api/v1/sakgaze/detections/latest")
def get_detections_latest(
    days: int = 7,
    limit: int = 1000,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:

    if not 1 <= days <= 90:
        raise HTTPException(
            status_code=400,
            detail="days must be between 1 and 90",
        )
    if not 1 <= limit <= 10000:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 10000",
        )

    try:
        return get_latest_sargassum(
            db,
            days=days,
            max_features=limit,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc.__class__.__name__}")


@app.get("/api/v1/weathernext/marine-alerts/latest")
def get_alerts_latest(
    days: int = 7,
    limit: int = 1000,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:

    if not 1 <= days <= 90:
        raise HTTPException(
            status_code=400,
            detail="days must be between 1 and 90",
        )
    if not 1 <= limit <= 10000:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 10000",
        )

    try:
        return get_latest_marine_alerts(
            db,
            days=days,
            max_features=limit,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc.__class__.__name__}")


@app.get("/api/v1/sakgaze/drift-predictions/latest")
def get_drift_latest(
    days: int = 7,
    limit: int = 1500,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:

    if not 1 <= days <= 90:
        raise HTTPException(
            status_code=400,
            detail="days must be between 1 and 90",
        )
    if not 1 <= limit <= 10000:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 10000",
        )

    try:
        return get_latest_drift_predictions(
            db,
            days=days,
            max_features=limit,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc.__class__.__name__}")
