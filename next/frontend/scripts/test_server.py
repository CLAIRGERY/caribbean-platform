#!/usr/bin/env python3
"""Local test server: serves dist/ plus a stub/fixture API so runtime probes complete.

Forced to be local-only: probes would otherwise hang on the unreachable Render
API. This server stubs the five GET endpoints using representative fixtures
from scripts/fixtures/ (or EMPTY when a fixture lacks entries), exercising the
app's full render path without live network.

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


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def do_GET(self):  # noqa: N802 (stdlib signature)
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

    def _json(self, payload: Any) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
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
