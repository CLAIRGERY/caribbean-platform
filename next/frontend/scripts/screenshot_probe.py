#!/usr/bin/env python3
"""Headless-Chrome screenshot probe of the built app.

Loads the page, waits for React/MapLibre boot, saves a screenshot, and scans
stderr for fatal console errors. Chrome is killed after the wait because the
app keeps timers alive (API retry loop), so headless Chrome never exits itself.
"""

import os
import pathlib
import subprocess
import sys

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5173/"
    shot = pathlib.Path("/tmp/sak_shot.png")
    log = pathlib.Path("/tmp/sak_sh.log")
    profile = pathlib.Path("/tmp/sakprof")
    if profile.exists():
        subprocess.run(["rm", "-rf", str(profile)], check=False)

    def devnull() -> "os._io.TextIOWrapper":
        return open(os.devnull, "w")

    logf = log.open("w")
    nd = devnull()
    try:
        proc = subprocess.Popen(
            [
                CHROME,
                f"--user-data-dir={profile}",
                "--headless",
                "--disable-gpu",
                "--no-first-run",
                "--window-size=1400,900",
                "--enable-unsafe-swiftshader",
                f"--screenshot={shot}",
                url,
            ],
            stdout=nd,
            stderr=logf,
        )
        try:
            proc.wait(timeout=18)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    finally:
        logf.close()
        nd.close()

    ok = shot.exists() and shot.stat().st_size > 10_000
    print(
        f"screenshot: exists={shot.exists()} "
        f"size={shot.stat().st_size if shot.exists() else 0}"
    )
    fatal: list[str] = []
    if log.exists():
        for line in log.read_text(errors="replace").splitlines():
            low = line.lower()
            if "uncaught" in low or "FATAL" in line:
                fatal.append(line)
    print(f"fatal console lines: {len(fatal)}")
    for line in fatal[:5]:
        print("  ", line[:220])
    if not ok:
        print("SCREENSHOT PROBE FAIL")
        return 1
    print("SCREENSHOT PROBE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
