"""URL normalisation tests (see app/database/url.py for the incident context)."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.src.db_url import normalize_database_url  # noqa: E402


def test_bare_postgresql_gets_psycopg2():
    assert normalize_database_url("postgresql://u:p@h:5432/db") == "postgresql+psycopg2://u:p@h:5432/db"


def test_postgres_scheme_is_rewritten():
    assert normalize_database_url("postgres://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"


def test_explicit_driver_is_preserved():
    for url in (
        "postgresql+psycopg2://u:p@h/db",
        "postgresql+psycopg://u:p@h/db",
        "sqlite:///tmp/x.db",
        "",
    ):
        assert normalize_database_url(url) == url
