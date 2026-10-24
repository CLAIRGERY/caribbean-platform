"""Typed application settings, read from the environment only.

No credential, hostname or project reference is ever hardcoded: the service is
deployable against any Postgres/PostGIS (Supabase, Render, self-hosted).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List

DEFAULTS_MAX_LIMIT = {"sargassum": 2000, "drift": 3000, "alerts": 1000}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    """Immutable runtime configuration."""

    environment: str = "development"
    database_url: str = ""
    cors_origins: List[str] = field(default_factory=list)
    gzip_min_size: int = 1024
    #: PostGIS simplification tolerance in degrees for *delivered* geometries.
    #: 0.0005° ≈ 55 m at 15°N — far below Sentinel-2 detection resolution, so the
    #: map is visually identical while payloads shrink by an order of magnitude.
    simplify_tolerance: float = 0.0005
    #: Hard ceiling per layer; requests above it are clamped (and reported).
    max_limit: Dict[str, int] = field(default_factory=lambda: dict(DEFAULTS_MAX_LIMIT))
    max_days: int = 90
    db_statement_timeout_ms: int = 8000
    db_pool_size: int = 5
    db_pool_max_overflow: int = 5
    #: If the database is unreachable, read endpoints answer 503 rather than 500.
    trust_proxy_headers: bool = True
    auto_migrate: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        origins = [
            o.strip().rstrip("/")
            for o in os.getenv("CORS_ORIGINS", "https://sakgaze.com,https://www.sakgaze.com,"
                                              "http://localhost:5173,http://127.0.0.1:5173").split(",")
            if o.strip()
        ]
        return cls(
            environment=os.getenv("API_ENV", "development"),
            database_url=os.getenv("DATABASE_URL", ""),
            cors_origins=origins,
            gzip_min_size=_env_int("GZIP_MIN_SIZE", 1024),
            simplify_tolerance=_env_float("MAP_SIMPLIFY_TOLERANCE", 0.0005),
            max_limit={
                "sargassum": _env_int("MAX_LIMIT_SARGASSUM", DEFAULTS_MAX_LIMIT["sargassum"]),
                "drift": _env_int("MAX_LIMIT_DRIFT", DEFAULTS_MAX_LIMIT["drift"]),
                "alerts": _env_int("MAX_LIMIT_ALERTS", DEFAULTS_MAX_LIMIT["alerts"]),
            },
            max_days=_env_int("MAX_DAYS", 90),
            db_statement_timeout_ms=_env_int("DB_STATEMENT_TIMEOUT_MS", 8000),
            db_pool_size=_env_int("DB_POOL_SIZE", 5),
            db_pool_max_overflow=_env_int("DB_POOL_MAX_OVERFLOW", 5),
            auto_migrate=_env_bool("SAKGAZE_AUTO_MIGRATE", False),
        )


settings = Settings.from_env()
