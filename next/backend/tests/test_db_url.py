"""Driver-normalisation guards for DATABASE_URL."""
from __future__ import annotations

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database.url import normalize_database_url  # noqa: E402


def test_bare_url_is_pinned_to_psycopg2():
    assert normalize_database_url("postgresql://u:p@h:5432/db").startswith("postgresql+psycopg2://")


def test_postgres_scheme_is_upgraded():
    assert normalize_database_url("postgres://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"


def test_explicit_driver_untouched():
    assert normalize_database_url("postgresql+psycopg2://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"
    assert normalize_database_url("") == ""
