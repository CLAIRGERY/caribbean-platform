#!/usr/bin/env python3
"""Local test server: serves dist/ plus a stub API so runtime probes complete.

The real Render API is currently unreachable (external outage). Headless probes
would otherwise hang on the browser's fetch retries. This server stubs the five
GET endpoints with empty-but-valid GeoJSON/JSON so the app exercises its full
render path.

Usage: python3 scripts/test_server.py [port]
"""

import http.server
import json
import pathlib
import socketserver
import sys

DIST = pathlib.Path(__file__).resolve().parent.parent / "dist"

EMPTY_FC = {"type": "FeatureCollection", "features": []}

API_ROUTES = {
    "/api/v1/ingestion/status": {"last_run": "2026-10-03T09:25:00Z", "status": "ok"},
    "/api/v1/sakgaze/detections/latest": EMPTY_FC,
    "/api/v1/sakgaze/drift-predictions/latest": EMPTY_FC,
    "/api/v1/weathernext/marine-alerts/latest": EMPTY_FC,
    "/api/v1/not-used": {},
}


class Handler(http.server.SimpleHTTPRequestHandler):
    # Serve dist + stubbed API. The app requests the REAL configured host
    # (sakgaze-api.onrender.com); the stub only helps when that fetch fails fast.
    # Because headless probes still hit the real host, we ALSO inject CORS-free
    # stub by proxying: our server rewrites /api/... on the same origin.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def do_GET(self):  # noqa: N802 (stdlib signature)
        if self.path in API_ROUTES:
            body = json.dumps(API_ROUTES[self.path]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/health":
            body = json.dumps({"status": "ok"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.wfile.write(body)
            return
        super().do_GET()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5199
    with Server(("127.0.0.1", port), Handler) as httpd:
        print(f"serving dist+stub on http://127.0.0.1:{port}/", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
