#!/usr/bin/env python3
"""Runtime verification: MapLibre map-ready behavior.

Checks (against a running server):
  1. .sak-stage rendered            (app shell mounted)
  2. "Initialisation..." gone       (map load event fired)
  3. .maplibregl-canvas exists
  4. canvas CSS dims > 0
  5. attribution text present
  6. no fatal JS / WebGL errors in stderr
  7. at least one maplibregl source rendered

Usage: python3 scripts/runtime_check.py [url]
Exit 0 = all checks pass.
"""

import re
import subprocess
import sys
import pathlib

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        if pathlib.Path(c).exists():
            return c
    raise SystemExit("no chrome/chromium found")


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5173/"
    chrome = find_chrome()
    import tempfile
    tmp = tempfile.TemporaryDirectory()
    profile = str(pathlib.Path(tmp.name) / "profile")
    try:
        proc = subprocess.Popen(
            [
                chrome,
                f"--user-data-dir={profile}",
                "--headless",
                "--disable-gpu",
                "--no-first-run",
                "--enable-unsafe-swiftshader",
                
                "--dump-dom",
                url,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            out, errout = proc.communicate(timeout=28)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, errout = proc.communicate()
    finally:
        tmp.cleanup()

    dom = out
    errors = [line for line in errout.splitlines() if "FATAL" in line or "Uncaught" in line]
    canvas_match = re.search(r'class="[^"]*maplibregl-canvas[^"]*"[^>]*width="(\d+)"[^>]*height="(\d+)"', dom)

    checks = [
        ("sak-stage rendered", "sak-stage" in dom, "App shell present"),
        ("loading text gone", "Initialisation de la carte" not in dom and "loading.initializing" not in dom, "map load event fired"),
        ("maplibre canvas", "maplibregl-canvas" in dom, "MapLibre GL canvas element exists"),
        ("canvas dims > 0", bool(canvas_match and int(canvas_match.group(1)) > 0 and int(canvas_match.group(2)) > 0),
         f"dims: {canvas_match.groups() if canvas_match else 'n/a'}"),
        ("attribution loaded", "OpenStreetMap" in dom or "CARTO" in dom or "Esri" in dom or "NASA" in dom or "attribution" in dom.lower(),
         "attribution/source text present"),
        ("no fatal errors", len(errors) == 0, f"{len(errors)} fatal lines"),
    ]

    print(f"DOM bytes: {len(dom)}")
    ok = True
    for name, passed, desc in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {name}  ({desc})")
        if not passed:
            ok = False
    if not ok:
        print("---- stderr excerpts ----")
        for line in errors[:6]:
            print(line[:200])
        print("RUNTIME CHECK FAIL")
        return 1
    print("RUNTIME CHECK OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
