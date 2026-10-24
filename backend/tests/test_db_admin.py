"""Schema-maintenance guards: additive-only DDL, no secrets in logs, bounded CLI."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.src import db_admin  # noqa: E402


def test_redacted_dsn_never_contains_password():
    dsn = "postgresql+psycopg2://postgres.abcdef:sup3r-s3cret@aws-0-eu-west-3.pooler.supabase.com:6543/postgres"
    shown = db_admin.redacted_dsn(dsn)
    assert "sup3r-s3cret" not in shown
    assert "abcdef" not in shown.split("@")[0]
    assert "aws-0-eu-west-3.pooler.supabase.com:6543/postgres" in shown


def test_migrations_are_additive_only():
    source = open(db_admin.__file__, encoding="utf-8").read()
    for destructive in ("DROP TABLE", "DROP COLUMN", "TRUNCATE", "DELETE FROM"):
        assert destructive not in source, f"db_admin must never emit {destructive}"
    for stmt in db_admin.COLUMNS:
        assert stmt[2].upper().startswith("VARCHAR")
    assert all(idx[1] in ("sargassum_detections", "drift_predictions", "marine_alerts") for idx in db_admin.INDEXES)


def test_spatial_indexes_are_built_concurrently():
    spatial = [idx for idx in db_admin.INDEXES if "GIST" in idx[2]]
    assert spatial, "expected at least one GIST index"
    assert all(idx[3] is True for idx in spatial), "GIST indexes must be CONCURRENTLY (API stays up)"


def test_cli_requires_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(SystemExit) as exc:
        db_admin.make_engine()
    assert "DATABASE_URL" in str(exc.value)


def test_cli_requires_an_action(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@127.0.0.1:1/db")
    with pytest.raises(SystemExit):
        db_admin.main([])


def test_lock_timeouts_default_to_bounded_values():
    assert db_admin.LOCK_TIMEOUT.endswith("s")
    assert int(db_admin.LOCK_TIMEOUT[:-1]) <= 30
    assert int(db_admin.STATEMENT_TIMEOUT[:-1]) <= 300
