"""Freshness semantics — the scientific-trust contract."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.status import SOURCE_THRESHOLDS, StatusService, freshness


class FakeResult:
    def __init__(self, first=None, scalar=None, rows=None):
        self._first = first
        self._scalar = scalar
        self._rows = rows or []

    def mappings(self):
        return self

    def first(self):
        return self._first

    def scalar(self):
        return self._scalar

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.rolled_back = False

    def execute(self, *_args, **_kwargs):
        return self._responses.pop(0)

    def rollback(self):
        self.rolled_back = True


def _scenario(sargassum_age_hours, count=10):
    now = datetime.now(timezone.utc)
    ts = now - timedelta(hours=sargassum_age_hours)
    responses = [
        FakeResult(first={"n": count, "ts": ts}),
        FakeResult(scalar=now),
        FakeResult(first={"n": 5, "ts": now - timedelta(hours=1)}),
        FakeResult(scalar=now),
        FakeResult(first={"n": 2, "ts": now - timedelta(hours=1)}),
        FakeResult(scalar=now),
        FakeResult(rows=[]),
    ]
    return FakeSession(responses)


def test_freshness_thresholds():
    t = {"live_hours": 48, "recent_hours": 168}
    assert freshness(1, t) == "LIVE"
    assert freshness(47.9, t) == "LIVE"
    assert freshness(48.1, t) == "RECENT"
    assert freshness(200, t) == "STALE"
    assert freshness(None, t) == "UNAVAILABLE"


def test_source_thresholds_are_ordered():
    for key, cfg in SOURCE_THRESHOLDS.items():
        assert cfg["live_hours"] < cfg["recent_hours"], key


def test_recent_acquisition_is_live():
    payload = StatusService().build(_scenario(6), api_version="2.0.0", environment="test")
    sargassum = payload["sources"][0]
    assert sargassum["freshness"] == "LIVE"
    assert sargassum["status" if "status" in sargassum else "key"] == "sargassum"


def test_old_acquisition_is_stale_and_degrades_status():
    payload = StatusService().build(_scenario(24 * 30), api_version="2.0.0", environment="test")
    assert payload["sources"][0]["freshness"] == "STALE"
    assert payload["status"] == "degraded"


def test_no_data_is_unavailable_not_unknown():
    now = datetime.now(timezone.utc)
    session = FakeSession([
        FakeResult(first={"n": 0, "ts": None}), FakeResult(scalar=None),
        FakeResult(first={"n": 0, "ts": None}), FakeResult(scalar=None),
        FakeResult(first={"n": 0, "ts": None}), FakeResult(scalar=None),
        FakeResult(rows=[]),
    ])
    payload = StatusService().build(session, api_version="2.0.0", environment="test")
    assert all(s["freshness"] == "UNAVAILABLE" for s in payload["sources"])
    assert payload["status"] == "degraded"


def test_database_error_degrades_without_raising():
    class Boom:
        def execute(self, *_a, **_k):
            raise Exception("(psycopg2.errors.QueryCanceled) canceling statement due to statement timeout")

        def rollback(self):
            self.rolled = True

    session = Boom()
    payload = StatusService().build(session, api_version="2.0.0", environment="test")
    assert payload["status"] == "degraded"
    assert payload["database"] == "unavailable"
    assert payload["warnings"]
    assert "psycopg2" not in str(payload)


def test_missing_session_reports_not_configured():
    payload = StatusService().build(None, api_version="2.0.0", environment="test")
    assert payload["database"] == "not_configured"
    assert payload["status"] == "degraded"
