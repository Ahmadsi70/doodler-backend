#!/usr/bin/env python3
"""
Launch local Inkplainer-OS (browser pen-draw UI) for a storybook still.

Inkplainer has no CLI API — this serves the vendored app and opens the browser.
Drop your page PNG into the Layers panel, pick Animal/Landscape style, Generate, Export.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "_vendor" / "Inkplainer-OS"


def _ensure_vendor() -> Path:
    if (VENDOR / "index.html").is_file():
        return VENDOR
    VENDOR.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "https://github.com/NadirWeb-App/Inkplainer-OS.git",
            str(VENDOR),
        ],
        check=True,
    )
    return VENDOR


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Open Inkplainer-OS for a still")
    p.add_argument(
        "--still",
        type=Path,
        default=ROOT / "out" / "storybook_fox_v4" / "pages" / "page_00.png",
    )
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args(argv)

    app = _ensure_vendor()
    still = Path(args.still).resolve()
    if not still.is_file():
        print(f"still missing: {still}", file=sys.stderr)
        return 1

    # Copy still next to a drop folder the user can find quickly
    drop = ROOT / "out" / "inkplainer_drop"
    drop.mkdir(parents=True, exist_ok=True)
    dest = drop / still.name
    shutil.copy2(still, dest)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(app), **kw)

        def log_message(self, fmt: str, *log_args) -> None:  # noqa: A003
            return

    httpd = ThreadingHTTPServer(("127.0.0.1", int(args.port)), Handler)
    Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{int(args.port)}/"
    print("Inkplainer:", url)
    print("Drop this PNG into Layers:", dest)
    print("Suggested: Drawing tab → stroke Sketch → Specialized Animal/Landscape → Generate → Export MP4")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
