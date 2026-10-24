#!/usr/bin/env python3
"""Local test server: serves dist/ plus a stub/fixture API so runtime probes complete.

Forced to be local-only: probes would otherwise hang on the unreachable Render
API. This server stubs the five GET endpoints using representative fixtures
from scripts/fixtures/ (or EMPTY when a fixture lacks entries), exercising the
app's full render path without live network.

Failure/empty injection (for layer-independence tests):
    SAK_FAIL=sargassum python3 scripts/test_server.py 5199   # that layer answers 503
    SAK_EMPTY=drift      python3 scripts/test_server.py 5199   # that layer answers an empty FC

Usage: python3 scripts/test_server.py [port]
"""

import http.server
import json
import pathlib
import socketserver
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
FIXTURES = ROOT / "scripts" / "fixtures"

EMPTY_FC: dict[str, Any] = {"type": "FeatureCollection", "features": []}


def load_fixture(name: str, fallback: Any) -> Any:
    f = FIXTURES / name
    if f.exists():
        return json.loads(f.read_text())
    return fallback


API_ROUTES: dict[str, Any] = {
    "/api/v1/ingestion/status": load_fixture("status.json", {"last_run": "2026-10-03T09:25:00Z", "status": "ok"}),
    "/api/v1/sakgaze/detections/latest": load_fixture("detections.json", EMPTY_FC),
    "/api/v1/sakgaze/drift-predictions/latest": load_fixture("drift.json", EMPTY_FC),
    "/api/v1/weathernext/marine-alerts/latest": load_fixture("marine.json", EMPTY_FC),
}

# Raw fixture file access for VITE_USE_TEST_FIXTURES=true (fetches /scripts/fixtures/<name>)
FIXTURE_PREFIX = "/scripts/fixtures/"

HEALTH = {"status": "ok"}

#: Layer keys accepted by SAK_FAIL / SAK_EMPTY.
LAYER_PATHS = {
    "sargassum": "/api/v1/sakgaze/detections/latest",
    "drift": "/api/v1/sakgaze/drift-predictions/latest",
    "marine": "/api/v1/weathernext/marine-alerts/latest",
    "status": "/api/v1/ingestion/status",
}
FAILING = {p.strip() for p in __import__("os").environ.get("SAK_FAIL", "").split(",") if p.strip()}
EMPTYING = {p.strip() for p in __import__("os").environ.get("SAK_EMPTY", "").split(",") if p.strip()}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def do_GET(self):  # noqa: N802 (stdlib signature)
        for layer, path in LAYER_PATHS.items():
            if self.path == path and layer in FAILING:
                self._json({"error": {"code": "UPSTREAM_UNAVAILABLE", "message": "injected"}}, status=503)
                return
            if self.path == path and layer in EMPTYING:
                self._json(EMPTY_FC)
                return
        if self.path in API_ROUTES:
            self._json(API_ROUTES[self.path])
            return
        if self.path == "/health":
            self._json(HEALTH)
            return
        if self.path.startswith(FIXTURE_PREFIX):
            name = self.path[len(FIXTURE_PREFIX):]
            f = FIXTURES / name
            if f.exists():
                self._json(json.loads(f.read_text()))
                return
        super().do_GET()

    def _json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5199
    with Server(("127.0.0.1", port), Handler) as httpd:
        print(f"serving dist+fixtures on http://127.0.0.1:{port}/", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
