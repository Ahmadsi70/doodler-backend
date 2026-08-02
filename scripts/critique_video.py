#!/usr/bin/env python3
"""
Critique a produced Story MP4 with Gemini video understanding.

Example:
  python scripts/critique_video.py --video out/pro_story_fox/final.mp4 --live --fa
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
except Exception:  # noqa: BLE001
    pass

from libraries.video_critique import analyze_story_video  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Gemini critique of Story final.mp4")
    p.add_argument(
        "--video",
        type=Path,
        default=ROOT / "out" / "pro_story_fox" / "final.mp4",
        help="Path to produced MP4",
    )
    p.add_argument("--story", default="", help="Story intent text")
    p.add_argument("--story-file", type=Path, default=None)
    p.add_argument("--out", type=Path, default=None, help="Report directory")
    p.add_argument("--live", action="store_true", help="Call Gemini (not mock)")
    p.add_argument("--mock", action="store_true")
    p.add_argument("--fa", action="store_true", help="Persian critique language")
    args = p.parse_args(argv)

    story = (args.story or "").strip()
    if args.story_file and args.story_file.is_file():
        story = args.story_file.read_text(encoding="utf-8").strip()
    elif not story:
        # Auto-pick story.txt beside the video when present
        side = args.video.parent / "story.txt"
        if side.is_file():
            story = side.read_text(encoding="utf-8").strip()

    mock = bool(args.mock) or not bool(args.live)
    report = analyze_story_video(
        args.video,
        story=story,
        language="fa" if args.fa else "en",
        mock=mock,
        output_dir=args.out or args.video.parent,
    )
    payload = json.dumps(report.to_json(), indent=2, ensure_ascii=False)
    try:
        print(payload)
    except UnicodeEncodeError:
        # Windows consoles may be cp1256/cp1252 — still persist full JSON on disk.
        sys.stdout.buffer.write((payload + "\n").encode("utf-8", errors="replace"))
    if report.report_json:
        print(f"\n# wrote {report.report_json}", file=sys.stderr)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
