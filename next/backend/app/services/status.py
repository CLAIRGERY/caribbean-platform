"""Scientific freshness reporting.

The product rule: never label historical data as live, never imply continuous
satellite coverage. Freshness is derived from the *data's own* timestamps and the
ingestion ledger — not from the fact that the API answered.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import classify_db_error

#: Thresholds are per source because the cadences are not comparable:
#: Sentinel-2 revisits the Caribbean every ~5 days, forecasts refresh every 6 h.
SOURCE_THRESHOLDS = {
    "sargassum": {"live_hours": 48.0, "recent_hours": 168.0,
                  "label": "Sargassum (Sentinel-2)", "note": "Sentinel-2 revisit ≈ 5 days"},
    "drift_predictions": {"live_hours": 12.0, "recent_hours": 48.0,
                          "label": "Dérive (prévisions)", "note": "forecast refresh every 6 h"},
    "marine_alerts": {"live_hours": 6.0, "recent_hours": 24.0,
                      "label": "Alertes marines", "note": "Open-Meteo / NOAA cadence"},
}

TABLES = {
    "sargassum": ("sargassum_detections", "acquisition_date"),
    "drift_predictions": ("drift_predictions", "created_at"),
    "marine_alerts": ("marine_alerts", "issued_at"),
}


def freshness(age_hours: Optional[float], thresholds: Dict[str, float]) -> str:
    if age_hours is None:
        return "UNAVAILABLE"
    if age_hours <= thresholds["live_hours"]:
        return "LIVE"
    if age_hours <= thresholds["recent_hours"]:
        return "RECENT"
    return "STALE"


class StatusService:
    """Builds the /status payload. Degrades gracefully, never raises."""

    def build(self, session: Optional[Session], *, api_version: str, environment: str) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        payload: Dict[str, Any] = {
            "status": "ok",
            "api_version": api_version,
            "environment": environment,
            "database": "not_configured",
            "generated_at": now.isoformat().replace("+00:00", "Z"),
            "sources": [],
            "latest_runs": [],
            "warnings": [],
        }
        if session is None:
            payload["status"] = "degraded"
            payload["warnings"].append("DATABASE_URL is not configured")
            return payload

        try:
            for key, (table, ts_col) in TABLES.items():
                thresholds = SOURCE_THRESHOLDS[key]
                row = session.execute(
                    text(f"SELECT COUNT(*) AS n, MAX({ts_col}) AS ts FROM {table}")
                ).mappings().first()
                count = int(row["n"] or 0) if row else 0
                latest: Optional[datetime] = row["ts"] if row else None
                age = None
                if latest is not None:
                    latest_aware = latest if latest.tzinfo else latest.replace(tzinfo=timezone.utc)
                    age = round((now - latest_aware).total_seconds() / 3600.0, 2)
                last_success = session.execute(
                    text(
                        "SELECT MAX(finished_at) FROM ingestion_runs "
                        "WHERE source = :s AND status = 'success'"
                    ),
                    {"s": key},
                ).scalar()
                payload["sources"].append({
                    "key": key,
                    "label": thresholds["label"],
                    "last_success": _iso(last_success),
                    "latest_data_timestamp": _iso(latest),
                    "record_count": count,
                    "freshness": freshness(age, thresholds),
                    "age_hours": age,
                    "thresholds_hours": {"live": thresholds["live_hours"], "recent": thresholds["recent_hours"]},
                    "note": thresholds["note"],
                })

            runs = session.execute(
                text(
                    "SELECT source, status, started_at, finished_at, records_downloaded, "
                    "records_inserted, records_skipped, records_rejected, "
                    "latest_data_timestamp, error "
                    "FROM ingestion_runs ORDER BY finished_at DESC NULLS LAST LIMIT 12"
                )
            ).mappings().all()
            payload["latest_runs"] = [
                {
                    "source": r["source"],
                    "status": r["status"],
                    "started_at": _iso(r["started_at"]),
                    "finished_at": _iso(r["finished_at"]),
                    "records_downloaded": int(r["records_downloaded"] or 0),
                    "records_inserted": int(r["records_inserted"] or 0),
                    "records_skipped": int(r["records_skipped"] or 0),
                    "records_rejected": int(r["records_rejected"] or 0),
                    "latest_data_timestamp": _iso(r["latest_data_timestamp"]),
                    "error": r["error"],
                }
                for r in runs
            ]
            payload["database"] = "ok"
            if any(s["freshness"] in ("STALE", "UNAVAILABLE") for s in payload["sources"]):
                payload["status"] = "degraded"
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            api_error = classify_db_error(exc)
            payload["status"] = "degraded"
            payload["database"] = "unavailable"
            payload["warnings"].append(api_error.message)
        return payload


def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.isoformat() + "Z"
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def source_keys() -> List[str]:
    return list(SOURCE_THRESHOLDS.keys())
