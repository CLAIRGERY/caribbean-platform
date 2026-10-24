"""Bounded write batching + single transient retry.

Regression target: run `40106574056` (2026-10-24) inserted 7 marine alerts and
skipped 153 sargassum detections, but a single 300-row INSERT of drift corridors
hit the 60 s statement timeout. One statement = one big lock and one big retry
unit, so writes are now chunked and a *transient* failure retries once — safe
only because `external_id` makes every write idempotent.
"""
from __future__ import annotations

import os
import sys

import pytest
from sqlalchemy.exc import OperationalError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.src.ingestion import runner  # noqa: E402


class FakeDb:
    def __init__(self, failures: int = 0):
        self.calls = 0
        self.rollbacks = 0
        self._failures = failures

    def rollback(self):
        self.rollbacks += 1


def ingester_recorder(features_per_call):
    def ingester(_db, features):
        features_per_call.append(len(features))
        return {"inserted": len(features), "skipped": 0, "rejected": 0}

    return ingester


def test_writes_are_chunked(monkeypatch):
    monkeypatch.setattr(runner, "WRITE_CHUNK_SIZE", 100)
    calls = []
    totals = runner._write_in_chunks(FakeDb(), ingester_recorder(calls),
                                     [{}] * 250, label="DRIFT", logger=runner.common.logger)
    assert calls == [100, 100, 50]
    assert totals == {"inserted": 250, "skipped": 0, "rejected": 0}


def test_single_chunk_when_below_threshold(monkeypatch):
    monkeypatch.setattr(runner, "WRITE_CHUNK_SIZE", 100)
    calls = []
    runner._write_in_chunks(FakeDb(), ingester_recorder(calls), [{}] * 7,
                            label="MARINE", logger=runner.common.logger)
    assert calls == [7]


def test_transient_database_error_retries_once(monkeypatch):
    monkeypatch.setattr(runner, "WRITE_CHUNK_SIZE", 10)
    monkeypatch.setattr(runner, "WRITE_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(runner, "WRITE_RETRY_DELAY_SECONDS", 0)
    db = FakeDb()
    attempts = {"n": 0}

    def flaky(_db, features):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise OperationalError("INSERT", {}, Exception("canceling statement due to statement timeout"))
        return {"inserted": len(features), "skipped": 0, "rejected": 0}

    totals = runner._write_in_chunks(db, flaky, [{}] * 10, label="DRIFT", logger=runner.common.logger)
    assert attempts["n"] == 2
    assert db.rollbacks == 1
    assert totals["inserted"] == 10


def test_retry_is_bounded(monkeypatch):
    monkeypatch.setattr(runner, "WRITE_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(runner, "WRITE_RETRY_DELAY_SECONDS", 0)

    def always_fails(_db, _features):
        raise OperationalError("INSERT", {}, Exception("canceling statement due to statement timeout"))

    with pytest.raises(OperationalError):
        runner._write_in_chunks(FakeDb(), always_fails, [{}] * 5,
                                label="DRIFT", logger=runner.common.logger)


def test_non_transient_error_is_not_retried(monkeypatch):
    monkeypatch.setattr(runner, "WRITE_RETRY_DELAY_SECONDS", 0)
    attempts = {"n": 0}

    def fails(_db, _features):
        attempts["n"] += 1
        raise ValueError("bad geometry")

    with pytest.raises(ValueError):
        runner._write_in_chunks(FakeDb(), fails, [{}], label="X", logger=runner.common.logger)
    assert attempts["n"] == 1
