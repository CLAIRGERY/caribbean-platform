#!/usr/bin/env python3
"""Headless-Chrome screenshot probe: capture the app at a given viewport.

Usage:
    python3 scripts/screenshot_probe.py <url> <width> <height> <out_png> [wait_s]

Chrome is killed after the wait because the app keeps API-retry timers alive,
so headless Chrome would otherwise never exit on its own.
"""

import os
import pathlib
import subprocess
import sys
from typing import IO

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
    width = src_width if (src_width := int(sys.argv[2]) if len(sys.argv) > 2 else 1440) else 1440
    height = int(sys.argv[3]) if len(sys.argv) > 3 else 900
    out_png = pathlib.Path(sys.argv[4]) if len(sys.argv) > 4 else pathlib.Path("/tmp/sak_shot.png")
    wait_s = int(sys.argv[5]) if len(sys.argv) > 5 else 14

    chrome = find_chrome()
    with tempfile_profile() as profile:
        log_path = out_png.with_suffix(".log")
        with log_path.open("w") as logf, open(os.devnull, "w") as nd:
            proc = subprocess.Popen(
                [
                    chrome,
                    f"--user-data-dir={profile}",
                    "--headless",
                    "--disable-gpu",
                    "--no-first-run",
                    f"--window-size={width},{height}",
                    "--enable-unsafe-swiftshader",
                    f"--screenshot={out_png}",
                    url,
                ],
                stdout=nd,
                stderr=logf,
            )
            try:
                proc.wait(timeout=wait_s)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    ok = out_png.exists() and out_png.stat().st_size > 50_000
    size = out_png.stat().st_size if out_png.exists() else 0
    print(f"screenshot: {out_png} exists={out_png.exists()} size={size}")
    fatal = [
        line
        for line in log_path.read_text(errors="replace").splitlines()
        if "uncaught" in line.lower() or "FATAL" in line
    ] if log_path.exists() else []
    print(f"fatal console lines: {len(fatal)}")
    print("SCREENSHOT PROBE OK" if ok else "SCREENSHOT PROBE FAIL")
    return 0 if ok else 1


def tempfile_profile():
    import tempfile

    tmp = tempfile.TemporaryDirectory()
    p = pathlib.Path(tmp.name) / "profile"
    return _Ctx(tmp, p)


class _Ctx:
    def __init__(self, tmp, profile: pathlib.Path):
        self.tmp = tmp
        self.profile = str(profile)

    def __enter__(self):
        return self.profile

    def __exit__(self, *exc):
        self.tmp.cleanup()
        return False


if __name__ == "__main__":
    sys.exit(main())
