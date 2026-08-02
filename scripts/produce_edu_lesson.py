#!/usr/bin/env python3
"""
Lane B — Kids Edu Micro-Lessons:
  Lane A story visuals + English TTS narration + ffmpeg mux.
  Must not import AnimateDiff / Lane C motion.

Example:
  python scripts/produce_edu_lesson.py --pack water --mock --narrate
  python scripts/produce_edu_lesson.py --pack water --live --still-backend flux --narrate
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

from libraries.edu_narration import (  # noqa: E402
    build_narration_plan,
    mux_video_with_narration,
    synthesize_cues,
)
from libraries.pro_quality_profile import PRO_FPS, PRO_HEIGHT, PRO_WIDTH  # noqa: E402
from libraries.storybook_pipeline import render_storybook  # noqa: E402
from libraries.storybook_scene_pack import (  # noqa: E402
    ARVIN_LAST_INVENTION,
    WATER_CYCLE_KIDS,
    plan_from_scene_pack,
)

PACKS = {
    "water": WATER_CYCLE_KIDS,
    "arvin": ARVIN_LAST_INVENTION,
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Produce layered educational story lesson")
    p.add_argument("--pack", choices=sorted(PACKS), default="water")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--target-sec", type=float, default=40.0)
    p.add_argument("--live", action="store_true")
    p.add_argument("--mock", action="store_true")
    p.add_argument("--still-backend", choices=("flux", "gemini", "auto"), default="flux")
    p.add_argument("--live-draw", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--narrate", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--voice", default="en-US-JennyNeural")
    p.add_argument("--width", type=int, default=PRO_WIDTH)
    p.add_argument("--height", type=int, default=PRO_HEIGHT)
    p.add_argument("--fps", type=int, default=PRO_FPS)
    args = p.parse_args(argv)

    pack = PACKS[args.pack]
    out = args.out or (ROOT / "out" / f"edu_{args.pack}")
    mock = bool(args.mock) or not bool(args.live)
    plan = plan_from_scene_pack(pack, target_sec=float(args.target_sec), crossfade_sec=0.45)
    still_backend = None if args.still_backend == "auto" else args.still_backend

    report = render_storybook(
        plan,
        out,
        width=int(args.width),
        height=int(args.height),
        fps=int(args.fps),
        mock=mock,
        still_backend=still_backend,
        live_draw=bool(args.live_draw),
    )
    report["pack"] = args.pack
    report["layer"] = "story_visuals"

    if args.narrate and report.get("ok") and report.get("final_mp4"):
        try:
            beats = [
                (
                    (p.narration or p.visual_action),
                    float(p.hold_sec),
                    (p.narration_en or ""),
                )
                for p in plan.pages
            ]
            cues = build_narration_plan(beats)
            audio_dir = out / "narration"
            tts = synthesize_cues(cues, audio_dir, voice=str(args.voice))
            narrated = out / "final_narrated.mp4"
            mux = mux_video_with_narration(
                Path(report["final_mp4"]), Path(tts["mix_mp3"]), narrated
            )
            report["narration"] = tts
            report["final_narrated_mp4"] = mux["path"]
            report["layer"] = "story_visuals+tts"
        except Exception as exc:  # noqa: BLE001
            report["narration_error"] = str(exc)
            report["layer"] = "story_visuals_only"

    (out / "unified_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    try:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    except UnicodeEncodeError:
        print(json.dumps(report, indent=2, ensure_ascii=True, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
