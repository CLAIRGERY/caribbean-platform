"""
FastAPI backend for SaKgaZé & Weathernext ingestion and map read APIs.
"""
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

# CORS — autorise le frontend (port 3000), Render, et production domains
origins = os.getenv("CORS_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000").split(",")
origins = [o.strip() for o in origins if o.strip()]
# Always allow Render preview URLs (*.onrender.com)
origins.append("https://*.onrender.com")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Ingestion endpoints
# ---------------------------------------------------------------------------
@app.post("/api/v1/sakgaze/detections", response_model=IngestResponse)
def post_detections(fc: GeoJSONFeatureCollection, db: Session = Depends(get_db)) -> Dict[str, Any]:
    result = ingest_sargassum_detections(db, fc.model_dump())
    return result


@app.post("/api/v1/sakgaze/drift-predictions", response_model=IngestResponse)
def post_drift(fc: GeoJSONFeatureCollection, db: Session = Depends(get_db)) -> Dict[str, Any]:
    result = ingest_drift_predictions(db, fc.model_dump())
    return result


@app.post("/api/v1/weathernext/marine-alerts", response_model=IngestResponse)
def post_alerts(fc: GeoJSONFeatureCollection, db: Session = Depends(get_db)) -> Dict[str, Any]:
    result = ingest_marine_alerts(db, fc.model_dump())
    return result


# ---------------------------------------------------------------------------
# Map read endpoints (ST_AsGeoJSON optimized)
# ---------------------------------------------------------------------------
@app.get("/api/v1/sakgaze/detections/latest")
def get_detections_latest(days: int = 7, db: Session = Depends(get_db)) -> Dict[str, Any]:
    if days <= 0 or days > 90:
        raise HTTPException(status_code=400, detail="days must be between 1 and 90")
    return get_latest_sargassum(db, days=days)


@app.get("/api/v1/weathernext/marine-alerts/latest")
def get_alerts_latest(days: int = 7, db: Session = Depends(get_db)) -> Dict[str, Any]:
    if days <= 0 or days > 90:
        raise HTTPException(status_code=400, detail="days must be between 1 and 90")
    return get_latest_marine_alerts(db, days=days)


@app.get("/api/v1/sakgaze/drift-predictions/latest")
def get_drift_latest(days: int = 7, db: Session = Depends(get_db)) -> Dict[str, Any]:
    if days <= 0 or days > 90:
        raise HTTPException(status_code=400, detail="days must be between 1 and 90")
    return get_latest_drift_predictions(db, days=days)
