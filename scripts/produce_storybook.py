#!/usr/bin/env python3
"""
Lane A — Kids Storybook Film:
  page stills + live pen + Ken Burns + crossfade (no cutouts, no Lane C motion).

Example:
  python scripts/produce_storybook.py --mock --title "Lantern Fox" --target-sec 20 \\
    --out out/storybook_fox --topic "A fox finds a lantern. Fireflies gather. Mist rises."

  python scripts/produce_storybook.py --live --critique --critique-fa \\
    --out out/storybook_fox_live --topic "..."
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

from agents.storybook_page_agent import plan_storybook  # noqa: E402
from agents.storybook_prompt_director import enrich_plan_prompts  # noqa: E402
from libraries.pro_quality_profile import PRO_FPS, PRO_HEIGHT, PRO_WIDTH  # noqa: E402
from libraries.storybook_pipeline import render_storybook  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Produce storybook page-film MP4")
    p.add_argument("--out", type=Path, default=ROOT / "out" / "storybook")
    p.add_argument("--topic", required=True)
    p.add_argument("--title", default="Story")
    p.add_argument("--language", default="en")
    p.add_argument("--target-sec", type=float, default=36.0)
    p.add_argument("--crossfade-sec", type=float, default=0.9)
    p.add_argument("--live", action="store_true")
    p.add_argument("--mock", action="store_true")
    p.add_argument(
        "--still-backend",
        choices=("flux", "gemini", "auto"),
        default="flux",
        help="Page still generator (default: FLUX.2 Klein via OpenRouter)",
    )
    p.add_argument(
        "--no-prompt-director",
        action="store_true",
        help="Skip live LLM prompt enrich (use crafted prompts only)",
    )
    p.add_argument(
        "--live-draw",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Draw each page live (ink→color) in the video (default: on)",
    )
    p.add_argument(
        "--reuse-pages",
        type=Path,
        default=None,
        help="Reuse existing page_XX.png stills (skip image generation)",
    )
    p.add_argument("--critique", action="store_true")
    p.add_argument("--critique-fa", action="store_true")
    p.add_argument("--width", type=int, default=PRO_WIDTH)
    p.add_argument("--height", type=int, default=PRO_HEIGHT)
    p.add_argument("--fps", type=int, default=PRO_FPS)
    args = p.parse_args(argv)

    mock = bool(args.mock) or not bool(args.live)
    still_paths: list[Path] | None = None
    if args.reuse_pages is not None:
        pages_dir = Path(args.reuse_pages)
        still_paths = sorted(pages_dir.glob("page_*.png"))
        if not still_paths:
            raise SystemExit(f"No page_*.png under {pages_dir}")
        # Reuse path: no live API, just recompose animation.
        mock = True

    plan = plan_storybook(
        args.topic,
        title=args.title,
        language=args.language,
        target_sec=float(args.target_sec),
        crossfade_sec=float(args.crossfade_sec),
    )
    # If reusing stills, trim/pad plan pages to match PNG count.
    if still_paths is not None and len(still_paths) != len(plan.pages):
        from libraries.storybook_contract import StorybookPage

        if len(still_paths) < len(plan.pages):
            plan.pages = plan.pages[: len(still_paths)]
        else:
            while len(plan.pages) < len(still_paths):
                last = plan.pages[-1]
                plan.pages.append(
                    StorybookPage(
                        index=len(plan.pages),
                        visual_action=last.visual_action,
                        hold_sec=last.hold_sec,
                        camera=last.camera,
                        shot=last.shot,
                        mood=last.mood,
                        concept=last.concept,
                        emotion=last.emotion,
                        camera_angle=last.camera_angle,
                        staging=last.staging,
                        visual_hook=last.visual_hook,
                        still_prompt=last.still_prompt,
                    )
                )

    prompt_mode = "craft"
    if not mock and not args.no_prompt_director and still_paths is None:
        plan = enrich_plan_prompts(plan)
        prompt_mode = "llm_enrich"
        (args.out).mkdir(parents=True, exist_ok=True)
        (args.out / "storybook_plan.json").write_text(
            plan.model_dump_json(indent=2), encoding="utf-8"
        )
    still_backend = None if args.still_backend == "auto" else args.still_backend
    report = render_storybook(
        plan,
        args.out,
        still_paths=still_paths,
        width=int(args.width),
        height=int(args.height),
        fps=int(args.fps),
        mock=mock,
        still_backend=still_backend,
        live_draw=bool(args.live_draw),
    )
    report["prompt_mode"] = prompt_mode
    report["still_backend_cli"] = args.still_backend
    if args.critique and report.get("ok") and report.get("final_mp4"):
        from libraries.video_critique import analyze_story_video

        critique = analyze_story_video(
            Path(report["final_mp4"]),
            story=args.topic,
            language="fa" if args.critique_fa else "en",
            mock=mock,
            output_dir=args.out,
        )
        report["video_critique"] = critique.to_json()
        report["video_critique_json"] = str(critique.report_json)
        (args.out / "unified_report.json").write_text(
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
