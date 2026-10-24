"""Healthy-by-default logging: one line per event, no secrets, no SQL payloads."""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any, Dict

_LOGGER = logging.getLogger("sakgaze.api")
_SECRET_KEYS = ("password", "token", "secret", "key", "dsn", "database_url", "authorization")


def setup_logging(level: str = "") -> None:
    lvl = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    handler = logging.StreamHandler(sys.stdout)
    if os.getenv("LOG_FORMAT", "text") == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(lvl)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update({k: ("***" if any(s in k.lower() for s in _SECRET_KEYS) else v)
                            for k, v in extra.items()})
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info).splitlines()[-1]
        return json.dumps(payload, default=str)


def log_event(event: str, **fields: Any) -> None:
    """Log a structured event, redacting anything that looks like a secret."""
    safe: Dict[str, Any] = {}
    for k, v in fields.items():
        if any(s in k.lower() for s in _SECRET_KEYS):
            safe[k] = "***"
        else:
            safe[k] = v
    _LOGGER.info(event, extra={"extra_fields": safe})
