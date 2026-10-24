"""Runner outcome tests: honest exit codes, isolated sources, no DDL.

These tests never touch a database: the collector and the run-metadata write are
both replaced by fakes. They verify the *contract* the workflow depends on.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.src.ingestion import runner  # noqa: E402
from backend.src.ingestion.errors import ErrorClass, MissingCredentials  # noqa: E402


@pytest.fixture(autouse=True)
def _no_db(monkeypatch):
    """Capture run-metadata writes instead of hitting Postgres."""
    recorded = []
    monkeypatch.setattr(runner, "_record_safe", lambda source, status, **kw: recorded.append((source, status, kw)))
    return recorded


def _feature(ts="2026-10-20T10:00:00Z"):
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[-61.5, 16.2], [-61.4, 16.2], [-61.4, 16.3], [-61.5, 16.2]]]},
        "properties": {"acquisition_date": ts, "surface_km2": 1.0},
    }


def _install_collector(monkeypatch, *, raw=None, features=None, exc=None):
    def fake_collector(source):
        def fetch():
            if exc:
                raise exc
            return raw or []

        def normalize(_raw):
            return features or []

        return fetch, normalize, "ingest_sargassum_idempotent"

    monkeypatch.setattr(runner, "_collector", fake_collector)


def test_empty_acquisition_exits_zero(monkeypatch):
    _install_collector(monkeypatch, raw=[], features=[])
    report = runner.run(["sargassum"])
    assert report["overall"] == "NO_NEW_DATA"
    assert report["exit_code"] == 0
    assert report["ok"] is True
    assert report["sources"]["sargassum"]["inserted"] == 0


def test_dry_run_does_not_write(monkeypatch):
    _install_collector(monkeypatch, raw=[{"id": 1}], features=[_feature()])
    report = runner.run(["sargassum"], dry_run=True)
    assert report["ok"] is True
    assert report["sources"]["sargassum"].get("dry_run") is True
    assert report["sources"]["sargassum"]["inserted"] == 0


def test_authentication_failure_is_fatal_with_exit_10(monkeypatch):
    _install_collector(monkeypatch, exc=Exception("invalid_grant: Invalid user credentials"))
    report = runner.run(["sargassum"])
    assert report["ok"] is False
    assert report["overall"] == "AUTHENTICATION_ERROR"
    assert report["exit_code"] == 10


def test_missing_credentials_is_configuration_error_exit_11(monkeypatch):
    _install_collector(monkeypatch, exc=MissingCredentials("CDSE_PASSWORD", "band streaming"))
    report = runner.run(["sargassum"])
    assert report["overall"] == "CONFIGURATION_ERROR"
    assert report["exit_code"] == 11


def test_database_failure_is_exit_12(monkeypatch):
    class OperationalError(Exception):
        pass

    _install_collector(monkeypatch, exc=OperationalError(
        "(psycopg2.errors.QueryCanceled) canceling statement due to statement timeout"))
    report = runner.run(["drift"])
    assert report["overall"] == "DATABASE_UNAVAILABLE"
    assert report["exit_code"] == 12


def test_one_failing_source_does_not_stop_the_others(monkeypatch, _no_db):
    calls = []

    def fake_collector(source):
        calls.append(source)

        def fetch():
            if source == "drift":
                raise Exception("503 Service Unavailable")
            return [_feature()]

        return fetch, lambda raw: raw, "ingest_sargassum_idempotent"

    monkeypatch.setattr(runner, "_collector", fake_collector)
    # avoid the real DB write path for the two healthy sources
    report = runner.run(["sargassum", "drift", "marine-alerts"], dry_run=True)
    assert calls == ["sargassum", "drift", "marine-alerts"]
    assert report["sources"]["sargassum"]["ok"] is True
    assert report["sources"]["drift"]["ok"] is False
    assert report["sources"]["marine-alerts"]["ok"] is True
    assert report["exit_code"] == 20


def test_main_returns_exit_code(monkeypatch, _no_db, capsys):
    _install_collector(monkeypatch, exc=Exception("invalid_client"))
    code = runner.main(["--source", "sargassum"])
    assert code == 10
    out = capsys.readouterr().out
    assert "AUTHENTICATION_ERROR" in out


def test_runner_never_runs_ddl():
    """Guard against the incident regression: no schema work in the hot path.

    Docstrings are exempt (they explain the incident); executable SQL strings and
    schema-helper imports are not.
    """
    import ast

    tree = ast.parse(open(runner.__file__, encoding="utf-8").read())
    docstrings = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant):
            docstrings.add(id(body[0].value))

    ddl = ("ALTER TABLE", "CREATE INDEX", "CREATE EXTENSION", "DROP ", "TRUNCATE")
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            for keyword in ddl:
                assert keyword not in node.value, f"runner must not execute DDL: {keyword!r}"
        if isinstance(node, ast.ImportFrom):
            names = {a.name for a in node.names}
            assert not ({"init_db", "create_all"} & names), f"runner must not import {names} for schema work"
