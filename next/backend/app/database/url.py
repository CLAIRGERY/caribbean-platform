"""Database URL normalisation (driver pinned to psycopg2).

SQLAlchemy 2.1 resolves a bare ``postgresql://`` URL to psycopg 3; this project
deploys ``psycopg2-binary``. Pinning the driver in the URL keeps the API working
regardless of the installed SQLAlchemy minor version (this exact mismatch broke
an ingestion run on 2026-10-24 with ``No module named 'psycopg'``).
"""
from __future__ import annotations


def normalize_database_url(url: str) -> str:
    if not url:
        return url
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url
