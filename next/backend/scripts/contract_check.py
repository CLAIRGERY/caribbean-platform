#!/usr/bin/env python3
"""Contract check: the paths and shapes the frontend actually reads vs. API v2.

The frontend composes every URL as ``VITE_API_BASE_URL + path``. This script
extracts those path literals from ``src/lib/api.ts`` and asserts that each one
resolves on the real FastAPI application, then checks the canonical v2
equivalent of every layer. No database is needed: the repository and session
dependencies are replaced with deterministic fakes.

Usage:
    cd workspace/backend-next && ./.venv/bin/python scripts/contract_check.py
Exit code 0 = every frontend path is served with the expected shape.
"""
from __future__ import annotations

import os
import re
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(BACKEND_DIR)
API_TS = os.path.join(WORKSPACE, "frontend-next", "src", "lib", "api.ts")
sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient  # noqa: E402

from app.database.session import get_optional_session, get_session  # noqa: E402
from app.main import create_app  # noqa: E402
from tests.conftest import FakeRepository, FakeSession, FakeStatusService  # noqa: E402

#: v1 path the frontend calls -> canonical v2 path (same shape).
V2_EQUIVALENT = {
    "/health": "/health",
    "/sakgaze/detections/latest": "/sargassum",
    "/sakgaze/drift-predictions/latest": "/drift",
    "/weathernext/marine-alerts/latest": "/marine-alerts",
    "/ingestion/status": "/status",
}

GEOJSON_PATHS = {
    "/sakgaze/detections/latest",
    "/sakgaze/drift-predictions/latest",
    "/weathernext/marine-alerts/latest",
}


def frontend_paths() -> list[str]:
    """Every single-quoted '/…' literal passed to the request() helper."""
    src = open(API_TS, encoding="utf-8").read()
    paths = set()
    for line in src.splitlines():
        if "request" not in line:
            continue
        for literal in re.findall(r"'(\/[A-Za-z0-9\-_/]+)'", line):
            paths.add(literal)
    return sorted(paths)


def check_geojson(client: TestClient, url: str) -> tuple[bool, str]:
    response = client.get(url)
    if response.status_code != 200:
        return False, f"HTTP {response.status_code}"
    body = response.json()
    if body.get("type") != "FeatureCollection" or not isinstance(body.get("features"), list):
        return False, "not a FeatureCollection"
    if "meta" not in body:
        return False, "missing meta"
    ctype = response.headers.get("content-type", "").split(";")[0]
    if ctype != "application/geo+json":
        return False, f"content-type {ctype}"
    return True, f"ok ({len(body['features'])} features, meta present)"


def check_json(client: TestClient, url: str, keys: tuple[str, ...]) -> tuple[bool, str]:
    response = client.get(url)
    if response.status_code != 200:
        return False, f"HTTP {response.status_code}"
    body = response.json()
    missing = [k for k in keys if k not in body]
    if missing:
        return False, f"missing keys {missing}"
    return True, "ok"


def main() -> int:
    paths = frontend_paths()
    if not paths:
        print("FAIL: could not extract any path from src/lib/api.ts")
        return 2
    unknown = [p for p in paths if p not in V2_EQUIVALENT]
    if unknown:
        print(f"FAIL: frontend calls paths with no v2 equivalent: {unknown}")
        return 2

    app = create_app(repository=FakeRepository(count=2), status_service=FakeStatusService())
    app.dependency_overrides[get_session] = lambda: FakeSession()
    app.dependency_overrides[get_optional_session] = lambda: FakeSession()
    client = TestClient(app)

    print(f"frontend paths ({len(paths)}): {', '.join(paths)}")
    failures = 0

    print("\n== /api/v1 (compatibility surface used by the current frontend) ==")
    for path in paths:
        if path in GEOJSON_PATHS:
            ok, detail = check_geojson(client, "/api/v1" + path)
        elif path == "/health":
            ok, detail = check_json(client, "/api/v1" + path, ("status", "service"))
        else:
            ok, detail = check_json(client, "/api/v1" + path, ("status", "database", "sources"))
        print(f"  {'PASS' if ok else 'FAIL'}  {('/api/v1' + path):<48} {detail}")
        failures += 0 if ok else 1

    print("\n== /api/v2 (canonical surface) ==")
    for path in paths:
        url = "/api/v2" + V2_EQUIVALENT[path]
        if path in GEOJSON_PATHS:
            ok, detail = check_geojson(client, url)
        elif path == "/health":
            ok, detail = check_json(client, url, ("status", "service", "version"))
        else:
            ok, detail = check_json(client, url, ("status", "database", "sources"))
        print(f"  {'PASS' if ok else 'FAIL'}  {url:<48} {detail}")
        failures += 0 if ok else 1

    print("\n== operations ==")
    for url, keys in (("/health", ("status", "service")),
                      ("/api/v2/status", ("status", "sources", "latest_runs")),
                      ("/api/v2/health/db", ("database", "configured"))):
        ok, detail = check_json(client, url, keys)
        print(f"  {'PASS' if ok else 'FAIL'}  {url:<48} {detail}")
        failures += 0 if ok else 1
    ok = client.get("/docs").status_code == 200
    print(f"  {'PASS' if ok else 'FAIL'}  {'/docs':<48} {'ok' if ok else 'not served'}")
    failures += 0 if ok else 1

    print(f"\n{'ALL PATHS OK' if failures == 0 else f'{failures} FAILURE(S)'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
