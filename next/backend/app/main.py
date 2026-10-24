"""SaKgaZé API v2 — application factory.

Design constraints:
* importing the module never touches the database;
* startup performs **no DDL** (Alembic owns the schema; a boot-time ALTER TABLE
  is what locked production in September 2026);
* every failure leaves through one structured envelope;
* GeoJSON responses are gzip-compressed above ``GZIP_MIN_SIZE`` by middleware.
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v2.routes import API_VERSION, compat, router as v2_router
from app.core.config import settings
from app.core.errors import ApiError
from app.core.logging import log_event, setup_logging
from app.database import session as db_session
from app.repositories.geospatial import GeospatialRepository
from app.schemas.geo import HealthResponse
from app.services.status import StatusService

SERVICE_NAME = "sakgaze-api-v2"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    log_event(
        "api_startup",
        service=SERVICE_NAME,
        version=API_VERSION,
        environment=settings.environment,
        database_configured=bool(settings.database_url),
        gzip_min_size=settings.gzip_min_size,
        simplify_tolerance=settings.simplify_tolerance,
    )
    try:
        yield
    finally:
        db_session.dispose()
        log_event("api_shutdown", service=SERVICE_NAME)


def create_app(
    *,
    repository: Optional[GeospatialRepository] = None,
    status_service: Optional[StatusService] = None,
) -> FastAPI:
    app = FastAPI(
        title="SaKgaZé API",
        version=API_VERSION,
        description=(
            "Caribbean sargassum intelligence API. GeoJSON layers are bounded, "
            "spatially filtered and simplified for delivery only."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.state.repository = repository or GeospatialRepository(settings.simplify_tolerance)
    app.state.status_service = status_service or StatusService()

    app.add_middleware(GZipMiddleware, minimum_size=settings.gzip_min_size)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Sakgaze-Simplified"],
        max_age=600,
    )

    @app.middleware("http")
    async def _request_context(request: Request, call_next):  # noqa: ANN001
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - converted below by handlers
            log_event("request_error", request_id=request_id, path=request.url.path,
                      duration_ms=round((time.perf_counter() - started) * 1000, 1))
            raise
        response.headers["X-Request-ID"] = request_id
        log_event("request", request_id=request_id, method=request.method,
                  path=request.url.path, status=response.status_code,
                  duration_ms=round((time.perf_counter() - started) * 1000, 1))
        return response

    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.envelope())

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "INVALID_PARAMETER",
                               "message": "one or more query parameters are invalid",
                               "details": {"errors": details}}},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail)}},
        )

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        # Never leak SQL, DSNs or stack traces to a client.
        log_event("unhandled_exception", error=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "unexpected server error"}},
        )

    app.include_router(v2_router, prefix="/api/v2", tags=["v2"])
    app.include_router(compat, prefix="/api/v1", tags=["v1-compat"], include_in_schema=False)

    @app.get("/health", response_model=HealthResponse, tags=["ops"])
    def health() -> HealthResponse:
        """Process liveness. Deliberately DB-free so Render probes never hang."""
        return HealthResponse(version=API_VERSION)

    @app.get("/api/v2/health/db", tags=["ops"])
    def health_db() -> Dict[str, Any]:
        ok = db_session.ping()
        return {
            "database": "ok" if ok else "unavailable",
            "configured": bool(settings.database_url),
        }

    return app


app = create_app()
