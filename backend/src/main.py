"""
FastAPI backend for SaKgaZé ingestion and map read APIs.
"""

import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    db_ok = "ok"
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = "error"
    return {
        "status": "ok" if db_ok == "ok" else "degraded",
        "service": "sakgaze-api",
        "database": db_ok,
    }


@app.get("/api/v1/ingestion/status")
def ingestion_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Read-only ingestion status for the three collectors."""
    return get_ingestion_status(db)


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
    db: Session = Depends(get_db),
) -> Dict[str, Any]:

    if not 1 <= days <= 90:
        raise HTTPException(
            status_code=400,
            detail="days must be between 1 and 90",
        )

    return get_latest_sargassum(
        db,
        days=days,
    )


@app.get("/api/v1/weathernext/marine-alerts/latest")
def get_alerts_latest(
    days: int = 7,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:

    if not 1 <= days <= 90:
        raise HTTPException(
            status_code=400,
            detail="days must be between 1 and 90",
        )

    return get_latest_marine_alerts(
        db,
        days=days,
    )


@app.get("/api/v1/sakgaze/drift-predictions/latest")
def get_drift_latest(
    days: int = 7,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:

    if not 1 <= days <= 90:
        raise HTTPException(
            status_code=400,
            detail="days must be between 1 and 90",
        )

    return get_latest_drift_predictions(
        db,
        days=days,
    )
