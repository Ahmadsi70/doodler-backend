#!/usr/bin/env python3
"""Produce a fixed story pack (e.g. Arvin 7 scenes) to MP4."""

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

from agents.storybook_prompt_director import enrich_plan_prompts  # noqa: E402
from libraries.pro_quality_profile import PRO_FPS, PRO_HEIGHT, PRO_WIDTH  # noqa: E402
from libraries.storybook_pipeline import render_storybook  # noqa: E402
from libraries.storybook_scene_pack import (  # noqa: E402
    ARVIN_LAST_INVENTION,
    WATER_CYCLE_KIDS,
    plan_from_scene_pack,
)

PACKS = {
    "arvin": ARVIN_LAST_INVENTION,
    "water": WATER_CYCLE_KIDS,
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Produce authored story pack MP4")
    p.add_argument("--pack", choices=sorted(PACKS), default="arvin")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--target-sec", type=float, default=49.0)
    p.add_argument("--live", action="store_true")
    p.add_argument("--mock", action="store_true")
    p.add_argument("--still-backend", choices=("flux", "gemini", "auto"), default="flux")
    p.add_argument("--live-draw", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--reuse-pages",
        type=Path,
        default=None,
        help="Reuse existing page_XX.png stills (skip image generation; recompose only)",
    )
    p.add_argument("--no-prompt-director", action="store_true")
    p.add_argument("--critique", action="store_true")
    p.add_argument("--critique-fa", action="store_true")
    p.add_argument("--width", type=int, default=PRO_WIDTH)
    p.add_argument("--height", type=int, default=PRO_HEIGHT)
    p.add_argument("--fps", type=int, default=PRO_FPS)
    args = p.parse_args(argv)

    pack = PACKS[args.pack]
    out = args.out or (ROOT / "out" / f"story_{args.pack}")
    mock = bool(args.mock) or not bool(args.live)
    still_paths: list[Path] | None = None
    if args.reuse_pages is not None:
        pages_dir = Path(args.reuse_pages)
        still_paths = sorted(pages_dir.glob("page_*.png"))
        if not still_paths:
            raise SystemExit(f"No page_*.png under {pages_dir}")
        mock = True
    plan = plan_from_scene_pack(pack, target_sec=float(args.target_sec))
    if still_paths is not None and len(still_paths) != len(plan.pages):
        if len(still_paths) < len(plan.pages):
            plan.pages = plan.pages[: len(still_paths)]
        # Extra PNGs beyond pack length are ignored.
    prompt_mode = "craft"
    if not mock and not args.no_prompt_director and still_paths is None:
        plan = enrich_plan_prompts(plan)
        prompt_mode = "llm_enrich"
    still_backend = None if args.still_backend == "auto" else args.still_backend
    report = render_storybook(
        plan,
        out,
        still_paths=still_paths,
        width=int(args.width),
        height=int(args.height),
        fps=int(args.fps),
        mock=mock,
        still_backend=still_backend,
        live_draw=bool(args.live_draw),
    )
    report["prompt_mode"] = prompt_mode
    report["pack"] = args.pack
    if args.critique and report.get("ok") and report.get("final_mp4"):
        from libraries.video_critique import analyze_story_video

        critique = analyze_story_video(
            Path(report["final_mp4"]),
            story=pack.topic,
            language="fa" if args.critique_fa else "en",
            mock=mock,
            output_dir=out,
        )
        report["video_critique"] = critique.to_json()
    out.mkdir(parents=True, exist_ok=True)
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
