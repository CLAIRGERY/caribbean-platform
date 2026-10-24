"""Database engine + session lifecycle.

Rules learned from production:
* the engine is created lazily, so importing the app never requires a database;
* per-session limits are applied with an explicit ``SET`` (the Supabase
  transaction pooler silently ignores libpq ``options``);
* ``pool_pre_ping`` + ``pool_recycle`` survive the pooler dropping idle sessions;
* nothing here creates or alters schema. Alembic owns the schema.
"""
from __future__ import annotations

import logging
from typing import Generator, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.errors import DatabaseNotConfigured
from app.database.url import normalize_database_url

logger = logging.getLogger("sakgaze.api.db")

_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


def get_engine() -> Engine:
    global _engine, _session_factory
    if _engine is not None:
        return _engine
    if not settings.database_url:
        raise DatabaseNotConfigured("DATABASE_URL is not configured")

    _engine = create_engine(
        normalize_database_url(settings.database_url),
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_max_overflow,
        pool_timeout=10,
        connect_args={
            "connect_timeout": 8,
            "application_name": "sakgaze-api-v2",
            # Bound every statement: a blocked table must never hold a request.
            "options": f"-c statement_timeout={settings.db_statement_timeout_ms}",
        },
    )

    @event.listens_for(_engine, "connect")
    def _set_session_limits(dbapi_connection, _record):  # noqa: ANN001
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute(f"SET statement_timeout = {int(settings.db_statement_timeout_ms)}")
            cursor.execute("SET lock_timeout = '5s'")
            cursor.execute("SET idle_in_transaction_session_timeout = '30s'")
            cursor.close()
        except Exception:  # noqa: BLE001 - tuning must never break a connection
            logger.debug("could not apply session limits", exc_info=True)

    _session_factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False, expire_on_commit=False)
    logger.info("database engine created (pool=%d)", settings.db_pool_size)
    return _engine


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request, always closed."""
    get_engine()
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()


def get_optional_session() -> Generator[Optional[Session], None, None]:
    """Dependency for endpoints that must degrade instead of failing.

    ``/status`` is the observability endpoint: if the database is not configured
    or the pool is exhausted it still answers 200 with ``database: unavailable``
    so the frontend can render freshness as UNAVAILABLE rather than blank.
    """
    try:
        engine = get_engine()
    except DatabaseNotConfigured:
        yield None
        return
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()


def ping() -> bool:
    try:
        engine = get_engine()
    except DatabaseNotConfigured:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        logger.warning("database ping failed", exc_info=True)
        return False


def dispose() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
