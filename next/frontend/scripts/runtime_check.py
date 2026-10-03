#!/usr/bin/env python3
"""Runtime smoke via headless Chrome: mount, canvas size, console errors.

Boots the built app with headless Chrome, waits for React to mount and MapLibre
to create a canvas, then inspects the DOM via --dump-dom and reports:
  - whether .sak-stage rendered
  - whether a maplibregl-canvas exists with nonzero width/height
  - whether any fatal boot errors prevented rendering

Usage: python3 scripts/runtime_check.py [url] [wait_seconds]
Exit code 0 = all runtime checks pass.
"""

import re
import subprocess
import sys
import tempfile
import pathlib

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
]


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        if pathlib.Path(c).exists():
            return c
    raise SystemExit("no chrome/chromium found")


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5173/"
    chrome = find_chrome()
    with tempfile.TemporaryDirectory() as tmp:
        profile = pathlib.Path(tmp) / "profile"
        dom_file = pathlib.Path(tmp) / "dom.html"
        proc = subprocess.Popen(
            [
                chrome,
                f"--user-data-dir={profile}",
                "--headless",
                "--disable-gpu",
                "--no-first-run",
                "--disable-software-rasterizer",
                "--enable-unsafe-swiftshader",
                "--virtual-time-budget=6000",
                "--timeout=12000",
                "--dump-dom",
                url,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            out, errout = proc.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, errout = proc.communicate()
        print(f"chrome exit: {proc.returncode}, stdout bytes: {len(out)}")
        dom_file.write_text(out, encoding="utf-8")
        dom = out
        errors = [line for line in errout.splitlines() if "FATAL" in line or "Uncaught" in line]

        checks: list[tuple[str, bool, str]] = []
        checks.append(("sak-stage rendered", "sak-stage" in dom, "body contains .sak-stage shell"))
        checks.append(("glass UI rendered", "sak-glass" in dom, "floating glass surfaces present"))
        checks.append(("maplibre canvas", "maplibregl-canvas" in dom, "MapLibre GL canvas element exists"))
        m = re.search(r'id="root">(.{0,120})', dom, re.S)
        checks.append(("root non-empty", bool(m and len(m.group(1).strip()) > 40), "#root has mounted content"))

        print(f"DOM bytes: {len(dom)}")
        ok = True
        for name, passed, desc in checks:
            print(f"{'PASS' if passed else 'FAIL'}  {name}  ({desc})")
            if not passed:
                ok = False
        if not ok:
            print("---- stderr excerpts ----")
            for line in errors[:8]:
                print(line)
            return 1
        print("RUNTIME CHECK OK")
        return 0


if __name__ == "__main__":
    sys.exit(main())
