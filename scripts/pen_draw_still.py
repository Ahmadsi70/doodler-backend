#!/usr/bin/env python3
"""Render a storybook still as a pen-draw reveal MP4 (headless Inkplainer-style)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libraries.storybook_pen_draw import render_pen_draw_mp4  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Pen-draw reveal from a still PNG")
    p.add_argument("--still", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--duration-sec", type=float, default=3.5)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--width", type=int, default=0)
    p.add_argument("--height", type=int, default=0)
    args = p.parse_args(argv)
    report = render_pen_draw_mp4(
        args.still,
        args.out,
        duration_sec=float(args.duration_sec),
        fps=int(args.fps),
        width=int(args.width) or None,
        height=int(args.height) or None,
    )
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
