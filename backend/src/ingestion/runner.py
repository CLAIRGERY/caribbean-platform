"""SaKgaZé ingestion runner.

Usage:
    python -m backend.src.ingestion.runner --source sargassum
    python -m backend.src.ingestion.runner --source drift
    python -m backend.src.ingestion.runner --source marine-alerts
    python -m backend.src.ingestion.runner --source all
"""
import argparse
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

# Ensure project root is importable when run as a module.
import os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.src.ingestion import common  # noqa: E402
from backend.src.database import SessionLocal, init_db  # noqa: E402
from backend.src.crud import (  # noqa: E402
    ingest_sargassum_idempotent,
    ingest_drift_idempotent,
    ingest_marine_alerts_idempotent,
    record_ingestion_run,
)

SOURCE_LABELS = {"sargassum": "SARGASSUM", "drift": "DRIFT", "marine-alerts": "MARINE"}
# Canonical DB source name (matches get_ingestion_status keys + table names)
SOURCE_DB_NAME = {
    "sargassum": "sargassum",
    "drift": "drift_predictions",
    "marine-alerts": "marine_alerts",
}


def _run_source(source: str) -> Dict[str, Any]:
    from backend.src.ingestion import sargassum as sak_mod
    from backend.src.ingestion import drift as drift_mod
    from backend.src.ingestion import marine_alerts as marine_mod

    label = SOURCE_LABELS[source]
    logger = common.logger
    started = time.time()
    logger.info("[%s] run started", label)

    downloaded = 0
    try:
        if source == "sargassum":
            raw = sak_mod.fetch_sargassum_detections()
            features = sak_mod.normalize_sargassum_detections(raw)
            ingester = ingest_sargassum_idempotent
            ts_key = "acquisition_date"
        elif source == "drift":
            raw = drift_mod.fetch_drift_predictions()
            features = drift_mod.normalize_drift_predictions(raw)
            ingester = ingest_drift_idempotent
            ts_key = "generated_at"
        elif source == "marine-alerts":
            raw = marine_mod.fetch_marine_alerts()
            features = marine_mod.normalize_marine_alerts(raw)
            ingester = ingest_marine_alerts_idempotent
            ts_key = "issued_at"
        else:
            raise ValueError(f"unknown source: {source}")

        downloaded = len(raw)
        logger.info("[%s] %d raw observations", label, downloaded)

        valid = [f for f in features if common.is_valid_feature(f)]
        logger.info("[%s] %d valid features", label, len(valid))
    except Exception as exc:  # noqa: BLE001
        logger.exception("[%s] fetch/normalize failed", label)
        _record(db=None, source=source, status="failed", error=str(exc))
        return {"status": "failed", "error": str(exc)}

    if not features:
        logger.warning("[%s] no features to ingest", label)
        _record(db=None, source=source, status="success", downloaded=downloaded, inserted=0)
        logger.info("[%s] run completed in %.1fs", label, time.time() - started)
        return {"status": "success", "downloaded": downloaded, "inserted": 0, "skipped": 0, "rejected": 0}

    db = SessionLocal()
    try:
        result = ingester(db, features)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("[%s] database write failed", label)
        _record(db=db, source=source, status="failed", error=str(exc), downloaded=downloaded)
        db.close()
        return {"status": "failed", "error": str(exc)}

    inserted = result.get("inserted", 0)
    skipped = result.get("skipped", 0)
    rejected = result.get("rejected", 0)
    logger.info("[%s] %d inserted", label, inserted)
    logger.info("[%s] %d skipped (duplicates)", label, skipped)

    latest_ts = _latest_ts(features, ts_key)
    status = "success" if inserted > 0 or skipped > 0 else "partial"
    _record(
        db=db,
        source=source,
        status=status,
        downloaded=downloaded,
        inserted=inserted,
        skipped=skipped,
        rejected=rejected,
        latest_data=latest_ts,
    )
    db.close()

    logger.info("[%s] newest acquisition: %s", label, latest_ts)
    logger.info("[%s] run completed in %.1fs", label, time.time() - started)
    return {
        "status": status,
        "downloaded": downloaded,
        "inserted": inserted,
        "skipped": skipped,
        "rejected": rejected,
        "latest_data_timestamp": latest_ts.isoformat() + "Z" if latest_ts else None,
    }


def _latest_ts(features: List[Dict[str, Any]], ts_key: str):
    from datetime import datetime as _dt
    best = None
    for f in features:
        v = f.get("properties", {}).get(ts_key)
        if isinstance(v, str):
            try:
                v = _dt.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                continue
        if isinstance(v, datetime):
            if best is None or v > best:
                best = v
    return best


def _record(db, source: str, status: str, *, downloaded: int = 0, inserted: int = 0,
            skipped: int = 0, rejected: int = 0, latest_data=None, error=None):
    db_source = SOURCE_DB_NAME.get(source, source)
    if db is None:
        db = SessionLocal()
        try:
            record_ingestion_run(
                db, db_source, status, downloaded=downloaded, inserted=inserted,
                skipped=skipped, rejected=rejected, latest_data=latest_data, error=error,
            )
        finally:
            db.close()
    else:
        record_ingestion_run(
            db, db_source, status, downloaded=downloaded, inserted=inserted,
            skipped=skipped, rejected=rejected, latest_data=latest_data, error=error,
        )


def run(source: str) -> Dict[str, Any]:
    init_db()
    if source == "all":
        results = {}
        for s in ("sargassum", "drift", "marine-alerts"):
            results[s] = _run_source(s)
        return results
    return _run_source(source)


def main() -> None:
    parser = argparse.ArgumentParser(description="SaKgaZé ingestion runner")
    parser.add_argument(
        "--source",
        choices=["sargassum", "drift", "marine-alerts", "all"],
        default="all",
        help="which collector to run",
    )
    args = parser.parse_args()
    result = run(args.source)
    # Print a compact summary for logs/CI.
    if args.source == "all":
        for k, v in result.items():
            common.logger.info("SUMMARY %s: %s", k, v)
    else:
        common.logger.info("SUMMARY %s: %s", args.source, result)


if __name__ == "__main__":
    main()
