"""Compatibility entry point.

The application lives in ``app/main.py`` (factory + routers). This shim keeps
``uvicorn main:app`` working for anyone (or any Render service) still pointing at
the old skeleton path.
"""
from app.main import app, create_app  # noqa: F401  (re-exported for uvicorn)

__all__ = ["app", "create_app"]
