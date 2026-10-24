"""SaKgaZé ingestion runner.

Design contract
---------------
* **No DDL.** The runner never touches the schema. Additive schema changes are
  applied by ``python -m backend.src.db_admin --migrate`` as a separate, bounded
  step. This is the fix for the September–October 2026 incident where a locked
  ``ALTER TABLE`` killed every run before acquisition even started.
* **Isolated sources.** Each collector runs with its own try/except, its own
  timing, its own classification. One broken upstream never hides the others.
* **Honest exit status.** ``main()`` returns a non-zero code for real failures,
  and 0 for ``SUCCESS`` / ``NO_NEW_DATA`` / ``PARTIAL_SUCCESS``. An empty
  Sentinel-2 window is a scientific outcome, not an outage.
* **Structured output.** One JSON object per run on stdout, plus a Markdown
  summary in ``$GITHUB_STEP_SUMMARY`` when present.

Usage::

    python -m backend.src.ingestion.runner --source all
    python -m backend.src.ingestion.runner --source drift --dry-run
    python -m backend.src.ingestion.runner --source marine-alerts --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Ensure project root is importable when run as a module.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.src.ingestion import common  # noqa: E402
from backend.src.ingestion.errors import (  # noqa: E402
    NON_FATAL,
    ErrorClass,
    classify_exception,
    exit_code,
    message_for,
)

SOURCES = ("sargassum", "drift", "marine-alerts")

SOURCE_LABELS = {"sargassum": "SARGASSUM", "drift": "DRIFT", "marine-alerts": "MARINE"}
# Canonical DB source name (matches get_ingestion_status keys + table names)
SOURCE_DB_NAME = {
    "sargassum": "sargassum",
    "drift": "drift_predictions",
    "marine-alerts": "marine_alerts",
}
SOURCE_TS_KEY = {"sargassum": "acquisition_date", "drift": "generated_at", "marine-alerts": "issued_at"}

#: Batch writes may legitimately take longer than an interactive API query.
#: The API keeps its 8 s bound; ingestion sessions raise it, explicitly and boundedly.
WRITE_STATEMENT_TIMEOUT = os.getenv("INGESTION_STATEMENT_TIMEOUT", "60s")

#: Bounded write batches. One statement per chunk keeps lock time and retry
#: granularity small (300-row single INSERT timed out on 2026-10-24).
WRITE_CHUNK_SIZE = int(os.getenv("INGESTION_WRITE_CHUNK", "100"))
#: Idempotent writes make a single retry on a transient DB error safe.
WRITE_MAX_ATTEMPTS = int(os.getenv("INGESTION_WRITE_ATTEMPTS", "2"))
WRITE_RETRY_DELAY_SECONDS = float(os.getenv("INGESTION_WRITE_RETRY_DELAY", "10"))


# ---------------------------------------------------------------------------
# Per-source execution
# ---------------------------------------------------------------------------
def db_preflight() -> Dict[str, Any]:
    """Read-only database diagnostic, logged once per run.

    Prints the server version and any session currently holding or waiting on a
    lock, so a `DATABASE_UNAVAILABLE` outcome is actionable from the CI log
    alone (no shell access to the database needed).
    """
    out: Dict[str, Any] = {"ok": False}
    try:
        from sqlalchemy import text

        from backend.src.database import engine

        with engine.connect() as conn:
            # The API bound (8 s) is too tight for pg_stat_activity with
            # pg_blocking_pids() on a busy pooler; give the diagnostic headroom.
            conn.execute(text("SET statement_timeout = '25s'"))
            out["server_version"] = conn.execute(text("SHOW server_version")).scalar()
            rows = conn.execute(text(
                """
                SELECT pid, state,
                       EXTRACT(EPOCH FROM (now() - COALESCE(xact_start, query_start)))::int AS age_s,
                       left(regexp_replace(COALESCE(query, ''), '\\s+', ' ', 'g'), 90) AS query,
                       cardinality(pg_blocking_pids(pid)) AS waits_for
                FROM pg_stat_activity
                WHERE datname = current_database() AND pid <> pg_backend_pid()
                  AND (state = 'idle in transaction' OR cardinality(pg_blocking_pids(pid)) > 0)
                ORDER BY age_s DESC
                LIMIT 10
                """
            )).mappings().all()
            out["blockers"] = [dict(r) for r in rows]
            out["ok"] = True
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{classify_exception(exc).value}: {exc}"
    common.logger.info("[DB] preflight: %s", json.dumps(out, default=str))
    return out


def _collector(source: str):
    """Import the collector lazily so a --dry-run never needs a DB driver."""
    if source == "sargassum":
        from backend.src.ingestion import sargassum as mod

        return mod.fetch_sargassum_detections, mod.normalize_sargassum_detections, "ingest_sargassum_idempotent"
    if source == "drift":
        from backend.src.ingestion import drift as mod

        return mod.fetch_drift_predictions, mod.normalize_drift_predictions, "ingest_drift_idempotent"
    if source == "marine-alerts":
        from backend.src.ingestion import marine_alerts as mod

        return mod.fetch_marine_alerts, mod.normalize_marine_alerts, "ingest_marine_alerts_idempotent"
    raise ValueError(f"unknown source: {source}")


def run_source(source: str, *, dry_run: bool = False) -> Dict[str, Any]:
    """Run one collector. Never raises: every outcome is classified."""
    label = SOURCE_LABELS[source]
    logger = common.logger
    started = time.time()
    logger.info("[%s] run started", label)
    base: Dict[str, Any] = {"source": source, "started_at": datetime.now(timezone.utc).isoformat()}

    try:
        fetch, normalize, ingester_name = _collector(source)
        raw = fetch()
        base["downloaded"] = len(raw)
        logger.info("[%s] %d raw observations", label, len(raw))

        features = normalize(raw)
        valid = [f for f in features if common.is_valid_feature(f)]
        rejected = len(features) - len(valid)
        base["features"] = len(features)
        base["rejected"] = rejected
        logger.info("[%s] %d valid features (%d rejected)", label, len(valid), rejected)
    except Exception as exc:  # noqa: BLE001 - classification is the whole point
        cls = classify_exception(exc)
        logger.error("[%s] fetch/normalize failed: %s — %s", label, cls.value, exc)
        logger.debug("%s", traceback.format_exc())
        _record_safe(source, "failed", error=f"{cls.value}: {exc}")
        return dict(
            base,
            error_class=cls.value,
            ok=cls in NON_FATAL,
            message=message_for(cls),
            error=str(exc),
            duration_s=round(time.time() - started, 1),
        )

    latest_ts = _latest_ts(valid, SOURCE_TS_KEY[source])

    if not valid:
        # A legitimate empty acquisition window: NOT an infrastructure failure.
        _record_safe(source, "success", downloaded=base["downloaded"],
                     error=ErrorClass.NO_NEW_DATA.value, latest_data=latest_ts)
        logger.warning("[%s] no observations in window -> NO_NEW_DATA (not a failure)", label)
        return dict(
            base,
            error_class=ErrorClass.NO_NEW_DATA.value,
            ok=True,
            message=message_for(ErrorClass.NO_NEW_DATA),
            inserted=0,
            skipped=0,
            latest_data_timestamp=_iso(latest_ts),
            duration_s=round(time.time() - started, 1),
        )

    if dry_run:
        logger.info("[%s] dry-run: skipping %d database writes", label, len(valid))
        return dict(
            base,
            error_class=ErrorClass.SUCCESS.value,
            ok=True,
            dry_run=True,
            message="dry-run: collectors reached upstream, no write performed",
            inserted=0,
            skipped=0,
            latest_data_timestamp=_iso(latest_ts),
            duration_s=round(time.time() - started, 1),
        )

    try:
        from backend.src import crud
        from backend.src.database import SessionLocal

        from sqlalchemy import text as _sql

        ingester = getattr(crud, ingester_name)
        db = SessionLocal()
        try:
            # Batch write bound: the API keeps 8 s, ingestion needs more headroom
            # but stays explicitly bounded (no unbounded statement).
            db.execute(_sql(f"SET statement_timeout = '{WRITE_STATEMENT_TIMEOUT}'"))
            db.execute(_sql("SET lock_timeout = '5s'"))
            result = _write_in_chunks(db, ingester, valid, label=label, logger=logger)
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        cls = classify_exception(exc)
        logger.error("[%s] database write failed: %s — %s", label, cls.value, exc)
        logger.debug("%s", traceback.format_exc())
        _record_safe(source, "failed", downloaded=base["downloaded"],
                     rejected=rejected, error=f"{cls.value}: {exc}", latest_data=latest_ts)
        return dict(
            base,
            error_class=cls.value,
            ok=cls in NON_FATAL,
            message=message_for(cls),
            error=str(exc),
            duration_s=round(time.time() - started, 1),
        )

    inserted = int(result.get("inserted", 0))
    skipped = int(result.get("skipped", 0))
    rejected += int(result.get("rejected", 0))

    if inserted > 0:
        cls = ErrorClass.SUCCESS if rejected == 0 else ErrorClass.PARTIAL_SUCCESS
        status = "success" if rejected == 0 else "partial"
    elif skipped > 0:
        cls = ErrorClass.NO_NEW_DATA  # everything already stored -> idempotent no-op
        status = "success"
    else:
        cls = ErrorClass.INVALID_SCIENTIFIC_DATA
        status = "partial"

    _record_safe(source, status, downloaded=base["downloaded"], inserted=inserted,
                 skipped=skipped, rejected=rejected, latest_data=latest_ts,
                 error=None if cls is ErrorClass.SUCCESS else cls.value)

    logger.info("[%s] inserted=%d skipped=%d rejected=%d class=%s (%.1fs)",
                label, inserted, skipped, rejected, cls.value, time.time() - started)
    return dict(
        base,
        error_class=cls.value,
        ok=cls in NON_FATAL,
        message=message_for(cls),
        inserted=inserted,
        skipped=skipped,
        rejected=rejected,
        latest_data_timestamp=_iso(latest_ts),
        duration_s=round(time.time() - started, 1),
    )


def _write_in_chunks(db, ingester, features, *, label: str, logger) -> Dict[str, Any]:
    """Write features in bounded chunks, with ONE retry on a transient DB error.

    Run 40106574056 showed why: a single 300-row INSERT of drift corridors hit the
    60 s statement timeout while the two other sources succeeded. One huge
    statement means one huge lock and one huge retry unit; chunks of
    ``INGESTION_WRITE_CHUNK`` rows keep every statement short.

    Writes are idempotent by ``external_id``, so retrying a chunk can never
    duplicate a row — that is what makes a retry safe here (and only here).
    """
    totals = {"inserted": 0, "skipped": 0, "rejected": 0}
    total = len(features)
    chunks = [features[i:i + WRITE_CHUNK_SIZE] for i in range(0, total, WRITE_CHUNK_SIZE)]
    for index, chunk in enumerate(chunks, start=1):
        started = time.time()
        attempt = 0
        while True:
            attempt += 1
            try:
                result = ingester(db, chunk)
                break
            except Exception as exc:  # noqa: BLE001
                cls = classify_exception(exc)
                transient = cls in (ErrorClass.DATABASE_UNAVAILABLE, ErrorClass.NETWORK_TIMEOUT)
                if attempt > WRITE_MAX_ATTEMPTS or not transient:
                    raise
                db.rollback()
                logger.warning(
                    "[%s] chunk %d/%d failed (%s); retrying in %.0fs (attempt %d/%d)",
                    label, index, len(chunks), cls.value, WRITE_RETRY_DELAY_SECONDS,
                    attempt, WRITE_MAX_ATTEMPTS,
                )
                time.sleep(WRITE_RETRY_DELAY_SECONDS)
        for key in totals:
            totals[key] += int(result.get(key, 0))
        logger.info(
            "[%s] chunk %d/%d: %d rows, inserted=%d skipped=%d (%.1fs)",
            label, index, len(chunks), len(chunk), int(result.get("inserted", 0)),
            int(result.get("skipped", 0)), time.time() - started,
        )
    return totals


def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.isoformat() + "Z"
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _latest_ts(features: List[Dict[str, Any]], ts_key: str) -> Optional[datetime]:
    best: Optional[datetime] = None
    for f in features:
        v = (f.get("properties") or {}).get(ts_key)
        if isinstance(v, str):
            try:
                v = datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                continue
        if isinstance(v, datetime):
            if v.tzinfo is not None:
                v = v.astimezone(timezone.utc).replace(tzinfo=None)
            if best is None or v > best:
                best = v
    return best


def _record_safe(source: str, status: str, **kwargs: Any) -> None:
    """Persist run metadata; never raises (DB outage must not mask the cause)."""
    try:
        from backend.src import crud
        from backend.src.database import SessionLocal

        db = SessionLocal()
        try:
            crud.record_ingestion_run(db, SOURCE_DB_NAME.get(source, source), status, **kwargs)
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        common.logger.warning("[%s] could not persist ingestion run metadata: %s", source, exc)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run(sources: List[str], *, dry_run: bool = False) -> Dict[str, Any]:
    preflight = None if dry_run else db_preflight()
    results: Dict[str, Any] = {}
    for source in sources:
        results[source] = run_source(source, dry_run=dry_run)

    fatal = [r for r in results.values() if not r["ok"]]
    if not fatal:
        overall = ErrorClass.NO_NEW_DATA if all(
            r["error_class"] == ErrorClass.NO_NEW_DATA.value for r in results.values()
        ) else ErrorClass.SUCCESS
    else:
        # Report the most actionable class: credential/schema problems first.
        priority = [
            ErrorClass.CONFIGURATION_ERROR,
            ErrorClass.AUTHENTICATION_ERROR,
            ErrorClass.DATABASE_UNAVAILABLE,
            ErrorClass.INVALID_SCIENTIFIC_DATA,
            ErrorClass.UPSTREAM_UNAVAILABLE,
            ErrorClass.RATE_LIMITED,
            ErrorClass.NETWORK_TIMEOUT,
            ErrorClass.PROCESSING_ERROR,
            ErrorClass.UNKNOWN_ERROR,
        ]
        present = {r["error_class"] for r in fatal}
        overall = next((c for c in priority if c.value in present), ErrorClass.UNKNOWN_ERROR)

    return {
        "overall": overall.value,
        "ok": not fatal,
        "exit_code": 0 if not fatal else exit_code(overall),
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "db_preflight": preflight,
        "sources": results,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="SaKgaZé ingestion runner")
    parser.add_argument("--source", choices=list(SOURCES) + ["all"], default="all")
    parser.add_argument("--dry-run", action="store_true",
                        help="run collectors but perform no database write")
    parser.add_argument("--json", action="store_true", help="print the full JSON report")
    parser.add_argument("--github-summary", action="store_true",
                        help="append a Markdown summary to $GITHUB_STEP_SUMMARY")
    args = parser.parse_args(argv)

    sources = list(SOURCES) if args.source == "all" else [args.source]
    report = run(sources, dry_run=args.dry_run)

    for name, result in report["sources"].items():
        common.logger.info("SUMMARY %s: %s", name, json.dumps(result, default=str))

    if args.json:
        print(json.dumps(report, default=str, indent=2))
    else:
        print(json.dumps({"overall": report["overall"], "exit_code": report["exit_code"],
                          "sources": {k: {"error_class": v["error_class"],
                                          "inserted": v.get("inserted", 0),
                                          "skipped": v.get("skipped", 0),
                                          "rejected": v.get("rejected", 0),
                                          "duration_s": v.get("duration_s")}
                                      for k, v in report["sources"].items()}},
                         default=str))

    if args.github_summary:
        write_step_summary(report)

    return int(report["exit_code"])


def write_step_summary(report: Dict[str, Any]) -> None:
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if not path:
        return
    icon = {"SUCCESS": "✅", "NO_NEW_DATA": "⚪️", "PARTIAL_SUCCESS": "🟡"}
    lines = ["## SaKgaZé ingestion", "", f"**Overall:** `{report['overall']}`", "",
             "| source | outcome | inserted | skipped | rejected | duration |",
             "|---|---|---|---|---|---|"]
    for name, r in report["sources"].items():
        cls = r["error_class"]
        mark = icon.get(cls, "❌")
        lines.append(
            f"| `{name}` | {mark} `{cls}` | {r.get('inserted', 0)} | {r.get('skipped', 0)} | "
            f"{r.get('rejected', 0)} | {r.get('duration_s', 0)}s |"
        )
    errors = [(n, r) for n, r in report["sources"].items() if not r["ok"]]
    if errors:
        lines += ["", "### Failures", ""]
        for name, r in errors:
            lines.append(f"- **{name}** — `{r['error_class']}`: {r.get('error') or r.get('message')}")
            if r["error_class"] == "AUTHENTICATION_ERROR":
                lines.append("  - action: rotate/repair the Copernicus CDSE credentials "
                             "(`CDSE_USERNAME`/`CDSE_PASSWORD`, S3 keys). No automatic retry loop.")
            if r["error_class"] == "DATABASE_UNAVAILABLE":
                lines.append("  - action: run `python -m backend.src.db_admin --inspect --terminate-blockers`.")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
