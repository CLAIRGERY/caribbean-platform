"""Database URL normalisation.

Why this exists
---------------
The DATABASE_URL secret is a plain ``postgresql://user:pass@host/db`` string (as
provided by Supabase/Render). SQLAlchemy 2.1 resolves a *bare* ``postgresql://``
URL to the **psycopg 3** driver, but this project ships ``psycopg2-binary``. The
mismatch surfaces only at first connection — during the ingestion run of
2026-10-24 it appeared as::

    [SARGASSUM] database write failed: CONFIGURATION_ERROR — No module named 'psycopg'

after 153 polygons had already been vectorised. Pinning the driver in the URL
makes the runtime independent of the SQLAlchemy minor version.
"""
from __future__ import annotations


def normalize_database_url(url: str) -> str:
    """Return a URL with an explicit psycopg2 driver."""
    if not url:
        return url
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url
