"""Database maintenance CLI: inspect, unblock and migrate the SaKgaZé schema.

Context — the 2026-09/10 ingestion incident
------------------------------------------
``init_db()`` used to run DDL (``ALTER TABLE ... ADD COLUMN IF NOT EXISTS``,
``CREATE INDEX ... USING GIST``) on *every* API boot and on *every* ingestion
run, with no ``lock_timeout``. When a session kept an ``ACCESS EXCLUSIVE`` lock
on ``sargassum_detections`` (an earlier job cancelled mid-DDL), every following
run queued behind it and was killed by the pooler's statement timeout after
30 s – 4 min, *before it ever fetched any satellite data*. Result: hundreds of
red GitHub notifications and zero new observations.

Design rules enforced here
--------------------------
1. DDL is a **separate, explicit, bounded** operation — never on the ingestion
   hot path, never on API boot (see ``database.init_db``).
2. Every DDL statement runs with ``lock_timeout`` so a blocked table produces a
   fast, explicit, classified failure instead of a 4-minute hang.
3. Existing objects are checked in the catalogue first: idempotent by
   construction, not by hoping ``IF NOT EXISTS`` behaves.
4. Indexes are built ``CONCURRENTLY`` in autocommit mode so a live API keeps
   serving while they are created.
5. Nothing destructive: only ``CREATE``/``ADD COLUMN IF NOT EXISTS``. No DROP,
   no data rewrite.

Usage::

    python -m backend.src.db_admin --inspect
    python -m backend.src.db_admin --terminate-blockers --migrate
    python -m backend.src.db_admin --migrate --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from backend.src.db_url import normalize_database_url

LOCK_TIMEOUT = os.getenv("SAKGAZE_DDL_LOCK_TIMEOUT", "5s")
STATEMENT_TIMEOUT = os.getenv("SAKGAZE_DDL_STATEMENT_TIMEOUT", "60s")
STALE_BLOCKER_SECONDS = int(os.getenv("SAKGAZE_STALE_BLOCKER_SECONDS", "60"))

# ---------------------------------------------------------------------------
# Schema catalogue expectations (single source of truth for additive changes)
# ---------------------------------------------------------------------------
COLUMNS = [
    # (table, column, ddl type, default)
    ("sargassum_detections", "external_id", "VARCHAR(64)", None),
    ("sargassum_detections", "source", "VARCHAR(50)", "'cdse_sentinel2'"),
    ("drift_predictions", "external_id", "VARCHAR(64)", None),
    ("drift_predictions", "source", "VARCHAR(50)", "'drift_engine'"),
    ("marine_alerts", "external_id", "VARCHAR(64)", None),
    ("marine_alerts", "source", "VARCHAR(50)", "'noaa_nhc_openmeteo'"),
]

INDEXES = [
    # (index name, table, definition, concurrently)
    ("idx_sargassum_external_id", "sargassum_detections", "(external_id)", False),
    ("idx_drift_external_id", "drift_predictions", "(external_id)", False),
    ("idx_alerts_external_id", "marine_alerts", "(external_id)", False),
    ("idx_sargassum_geom", "sargassum_detections", "USING GIST (geometry)", True),
    ("idx_drift_geom", "drift_predictions", "USING GIST (geometry)", True),
    ("idx_alerts_geom", "marine_alerts", "USING GIST (geometry)", True),
]


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------
def database_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise SystemExit(
            "CONFIGURATION_ERROR: DATABASE_URL is not set. "
            "Ingestion and schema maintenance cannot run without it."
        )
    return url


def redacted_dsn(url: str) -> str:
    """host:port/db only — never the password (logs are public artefacts)."""
    try:
        from sqlalchemy.engine import make_url

        u = make_url(url)
        return f"{u.host}:{u.port}/{u.database}"
    except Exception:  # noqa: BLE001
        return "<unparseable DATABASE_URL>"


def make_engine() -> Engine:
    """AUTOCOMMIT engine: required for CREATE INDEX CONCURRENTLY."""
    return create_engine(
        normalize_database_url(database_url()),
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10, "application_name": "sakgaze-db-admin"},
    )


def _session_settings(conn) -> None:
    # Applied per connection: pgbouncer (Supabase transaction pooler) ignores the
    # libpq ``options`` startup parameter, which is why the old engine-level
    # statement_timeout never took effect.
    conn.execute(text(f"SET lock_timeout = '{LOCK_TIMEOUT}'"))
    conn.execute(text(f"SET statement_timeout = '{STATEMENT_TIMEOUT}'"))
    conn.execute(text("SET idle_in_transaction_session_timeout = '30s'"))


# ---------------------------------------------------------------------------
# Inspection
# ---------------------------------------------------------------------------
def _table_columns(conn, table: str) -> List[str]:
    rows = conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = :t"
        ),
        {"t": table},
    ).all()
    return sorted(r[0] for r in rows)


def _index_names(conn, table: str) -> List[str]:
    rows = conn.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE schemaname = current_schema() AND tablename = :t"
        ),
        {"t": table},
    ).all()
    return sorted(r[0] for r in rows)


def _blockers(conn) -> List[Dict[str, Any]]:
    """Sessions that hold or wait on a lock for longer than the threshold."""
    sql = text(
        """
        SELECT a.pid,
               a.state,
               a.wait_event_type,
               a.wait_event,
               EXTRACT(EPOCH FROM (now() - COALESCE(a.xact_start, a.query_start)))::int AS age_s,
               left(regexp_replace(COALESCE(a.query, ''), '\\s+', ' ', 'g'), 120) AS query,
               pg_blocking_pids(a.pid) AS blocked_by
        FROM pg_stat_activity a
        WHERE a.pid <> pg_backend_pid()
          AND a.datname = current_database()
          AND (
                (a.state = 'idle in transaction' AND a.xact_start < now() - make_interval(secs => :stale))
             OR (cardinality(pg_blocking_pids(a.pid)) > 0)
             OR (a.wait_event_type = 'Lock' AND a.query_start < now() - make_interval(secs => :stale))
          )
        ORDER BY age_s DESC
        """
    )
    return [dict(r._mapping) for r in conn.execute(sql, {"stale": STALE_BLOCKER_SECONDS}).all()]


def inspect(engine: Engine, *, terminate: bool = False) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "dsn": redacted_dsn(engine.url.render_as_string(hide_password=True)),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "tables": {},
    }
    with engine.connect() as conn:
        _session_settings(conn)
        report["server_version"] = conn.execute(text("SHOW server_version")).scalar()
        try:
            report["postgis"] = conn.execute(text("SELECT postgis_version()")).scalar()
        except Exception:  # noqa: BLE001
            report["postgis"] = None
            report["postgis_error"] = "extension not installed / not visible"

        for table in ("sargassum_detections", "drift_predictions", "marine_alerts", "ingestion_runs"):
            cols = _table_columns(conn, table)
            report["tables"][table] = {
                "exists": bool(cols),
                "columns": cols,
                "indexes": _index_names(conn, table) if cols else [],
                "rows": _row_count(conn, table) if cols else 0,
            }

        blockers = _blockers(conn)
        report["blockers"] = blockers
        if terminate and blockers:
            report["terminated"] = _terminate(conn, blockers)
    return report


def _row_count(conn, table: str) -> Optional[int]:
    try:
        # exact counts are acceptable here: this runs on a maintenance cadence,
        # not on the API request path.
        return int(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)
    except Exception:  # noqa: BLE001
        return None


def _terminate(conn, blockers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Kill sessions that are stuck holding or waiting on a lock.

    Only sessions that are idle-in-transaction or explicitly waiting on a lock
    are targeted — never a session that is actively executing a legitimate
    ingestion/API query.
    """
    killed: List[Dict[str, Any]] = []
    for b in blockers:
        pid = b["pid"]
        idle_stuck = b.get("state") == "idle in transaction"
        waiting = bool(b.get("blocked_by"))
        if not (idle_stuck or waiting):
            continue
        try:
            conn.execute(text("SELECT pg_terminate_backend(:pid, 5000)"), {"pid": pid})
            killed.append({"pid": pid, "state": b.get("state"), "age_s": b.get("age_s")})
        except Exception as exc:  # noqa: BLE001
            killed.append({"pid": pid, "error": type(exc).__name__})
    return killed


# ---------------------------------------------------------------------------
# Additive migration
# ---------------------------------------------------------------------------
def migrate(engine: Engine) -> Dict[str, Any]:
    applied: List[str] = []
    skipped: List[str] = []
    failed: List[Dict[str, str]] = []

    with engine.connect() as conn:
        _session_settings(conn)
        for table, column, sql_type, default in COLUMNS:
            cols = _table_columns(conn, table)
            if not cols:
                skipped.append(f"{table}.{column} (table absent)")
                continue
            if column in cols:
                skipped.append(f"{table}.{column} (present)")
                continue
            ddl = f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {sql_type}"
            if default is not None:
                ddl += f" DEFAULT {default}"
            try:
                conn.execute(text(ddl))
                applied.append(ddl)
            except Exception as exc:  # noqa: BLE001
                failed.append({"statement": ddl, "error": f"{type(exc).__name__}: {exc}"})
                break

        if not failed:
            for name, table, definition, concurrently in INDEXES:
                if not _table_columns(conn, table):
                    skipped.append(f"{name} (table absent)")
                    continue
                if name in _index_names(conn, table):
                    skipped.append(f"{name} (present)")
                    continue
                ddl = (
                    f"CREATE INDEX {'CONCURRENTLY ' if concurrently else ''}"
                    f"IF NOT EXISTS {name} ON {table} {definition}"
                )
                try:
                    conn.execute(text(ddl))
                    applied.append(ddl)
                except Exception as exc:  # noqa: BLE001
                    failed.append({"statement": ddl, "error": f"{type(exc).__name__}: {exc}"})

    return {"applied": applied, "skipped": skipped, "failed": failed, "ok": not failed}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="SaKgaZé database maintenance")
    parser.add_argument("--inspect", action="store_true", help="report schema, row counts and lock blockers")
    parser.add_argument("--terminate-blockers", action="store_true", help="kill sessions stuck on locks")
    parser.add_argument("--migrate", action="store_true", help="apply additive schema changes")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--github-summary", action="store_true", help="append a summary to $GITHUB_STEP_SUMMARY")
    args = parser.parse_args(argv)

    if not (args.inspect or args.migrate):
        parser.error("nothing to do: pass --inspect and/or --migrate")

    engine = make_engine()
    payload: Dict[str, Any] = {}
    exit_status = 0

    try:
        if args.inspect or args.terminate_blockers:
            payload["inspection"] = inspect(engine, terminate=args.terminate_blockers)
        if args.migrate:
            payload["migration"] = migrate(engine)
            if not payload["migration"]["ok"]:
                exit_status = 30
                failure = payload["migration"]["failed"][0]
                payload["error_class"] = "DATABASE_UNAVAILABLE"
                payload["message"] = failure["error"]
    except Exception as exc:  # noqa: BLE001
        payload["error_class"] = "DATABASE_UNAVAILABLE"
        payload["message"] = f"{type(exc).__name__}: {exc}"
        exit_status = 12
    finally:
        engine.dispose()

    if args.json:
        print(json.dumps(payload, default=str, indent=2))
    else:
        _print_human(payload)

    if args.github_summary:
        _github_summary(payload)

    return exit_status


def _print_human(payload: Dict[str, Any]) -> None:
    insp = payload.get("inspection")
    if insp:
        print(f"DSN       : {insp['dsn']}")
        print(f"PostgreSQL: {insp.get('server_version')}  PostGIS: {insp.get('postgis')}")
        for table, meta in insp["tables"].items():
            print(f"  {table:24s} exists={meta['exists']!s:5s} rows={meta['rows']} indexes={len(meta['indexes'])}")
        print(f"  blockers: {len(insp.get('blockers') or [])}")
        for b in insp.get("blockers") or []:
            print(f"    pid={b['pid']} state={b['state']} age={b['age_s']}s blocked_by={b['blocked_by']}")
        for k in insp.get("terminated") or []:
            print(f"    terminated pid={k['pid']} state={k.get('state')} age={k.get('age_s')}s")
    mig = payload.get("migration")
    if mig:
        print(f"DDL applied: {len(mig['applied'])}  skipped: {len(mig['skipped'])}  failed: {len(mig['failed'])}")
        for stmt in mig["applied"]:
            print(f"  + {stmt}")
        for stmt in mig["failed"]:
            print(f"  ! {stmt['statement']} -> {stmt['error']}")
    if payload.get("message"):
        print(f"{payload.get('error_class')}: {payload['message']}")


def _github_summary(payload: Dict[str, Any]) -> None:
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = ["## SaKgaZé — database maintenance", ""]
    insp = payload.get("inspection")
    if insp:
        lines.append(f"- DSN: `{insp['dsn']}`")
        lines.append(f"- PostgreSQL `{insp.get('server_version')}` / PostGIS `{insp.get('postgis')}`")
        lines.append("")
        lines.append("| table | exists | rows | indexes |")
        lines.append("|---|---|---|---|")
        for table, meta in insp["tables"].items():
            lines.append(f"| `{table}` | {meta['exists']} | {meta['rows']} | {len(meta['indexes'])} |")
        blockers = insp.get("blockers") or []
        lines.append("")
        lines.append(f"- lock blockers: **{len(blockers)}**")
        for k in insp.get("terminated") or []:
            lines.append(f"- terminated stuck session pid={k['pid']} ({k.get('age_s')}s)")
    mig = payload.get("migration")
    if mig:
        lines.append("")
        lines.append(f"- DDL applied: **{len(mig['applied'])}** / skipped {len(mig['skipped'])} / failed {len(mig['failed'])}")
        for stmt in mig["failed"]:
            lines.append(f"- ❌ `{stmt['statement']}` → {stmt['error']}")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
