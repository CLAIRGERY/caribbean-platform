"""SaKgaZe Next - backend skeleton (FastAPI + SQLAlchemy + PostGIS-ready).

Frontend NEVER depends on this being finished; it mirrors the v1 GET contract
so swapping VITE_API_BASE_URL is enough when this backend is ready.
"""

import gzip
import os
from typing import Any

from fastapi import FastAPI, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="SaKgaZe API v2 (skeleton)", version="2.0.0")
app.add_middleware(GZipMiddleware, minimum_size=1024)

_cors = os.getenv("CORS_ORIGINS", "")
_origins = [o.strip() for o in _cors.split(",") if o.strip()] or ["*"]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])

# DATABASE_URL consumed verbatim - never hardcode host/password/project ref.
DATABASE_URL = os.getenv("DATABASE_URL", "")

EMPTY_FC = {"type": "FeatureCollection", "features": []}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v2/status")
def status() -> dict[str, Any]:
    return {"db_configured": bool(DATABASE_URL), "version": "2.0.0"}


def _fc_response(payload: dict[str, Any]) -> Response:
    body = gzip.compress(str(payload).encode()) if False else json_encode(payload)
    return Response(content=body, media_type="application/geo+json", headers={"Content-Encoding": "identity"})


def json_encode(data: dict[str, Any]) -> bytes:
    import json
    return json.dumps(data, separators=(",", ":")).encode()


@app.get("/api/v2/sargassum")
def sargassum(limit: int = 1000, days: int = 30, bbox: str | None = None) -> Response:
    # TODO: PostGIS ST_SimplifyPreserveTopology + ST_AsGeoJSON + GZip; bounded queries.
    return _fc_response(EMPTY_FC)


@app.get("/api/v2/drift")
def drift(limit: int = 1500, bbox: str | None = None) -> Response:
    return _fc_response(EMPTY_FC)


@app.get("/api/v2/marine-alerts")
def marine_alerts(limit: int = 500, bbox: str | None = None) -> Response:
    return _fc_response(EMPTY_FC)
