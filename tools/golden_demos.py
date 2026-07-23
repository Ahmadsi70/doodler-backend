"""
Story golden demos — Light slideshow pixel QA.

Fixtures: ``fixtures/golden/<demo_id>/`` with ``meta.json``, ``expected/hashes.json``.

Refresh::

  $env:ANIMATION_DETERMINISTIC_SLIDES=1
  $env:UPDATE_GOLDENS=1
  python -m pytest tests/test_story_golden.py -q
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_GOLDEN_ROOT = _ROOT / "fixtures" / "golden"

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from tools.pixel_qa import (
        PixelQAReport,
        compare_hashes,
        compare_structural,
        hash_png_dir,
        structural_probe,
        write_hashes_json,
    )
except ImportError:
    from .pixel_qa import (  # type: ignore
        PixelQAReport,
        compare_hashes,
        compare_structural,
        hash_png_dir,
        structural_probe,
        write_hashes_json,
    )


@dataclass
class DemoResult:
    demo_id: str
    kind: str
    passed: bool
    reports: list[PixelQAReport] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "demo_id": self.demo_id,
            "kind": self.kind,
            "passed": self.passed,
            "notes": self.notes,
            "artifacts": self.artifacts,
            "reports": [r.to_dict() for r in self.reports],
        }


def golden_root() -> Path:
    return _GOLDEN_ROOT


def list_demos() -> list[str]:
    root = golden_root()
    if not root.is_dir():
        return []
    return sorted(
        p.name for p in root.iterdir() if p.is_dir() and (p / "meta.json").is_file()
    )


def list_golden_demos() -> list[str]:
    return list_demos()


def load_demo_meta(demo_id: str) -> dict[str, Any]:
    return json.loads((golden_root() / demo_id / "meta.json").read_text(encoding="utf-8"))


def load_brief(demo_id: str) -> str:
    brief_path = golden_root() / demo_id / "brief.txt"
    if brief_path.is_file():
        return brief_path.read_text(encoding="utf-8").strip()
    return str(load_demo_meta(demo_id).get("brief") or "")


def run_demo(
    demo_id: str,
    out_dir: Path | str,
    *,
    update: bool = False,
) -> DemoResult:
    from runtime.light_slideshow import render_from_prompt
    from tools.studio_profiles import find_ffmpeg

    os.environ["ANIMATION_DETERMINISTIC_SLIDES"] = "1"
    meta = load_demo_meta(demo_id)
    if str(meta.get("kind") or "") == "props_contract":
        return DemoResult(
            demo_id,
            "props_contract",
            True,
            notes="use tests/test_story_pro_golden.py — not pixel Light QA",
        )
    brief = load_brief(demo_id)
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return DemoResult(demo_id, "light_slideshow", False, notes="ffmpeg not found")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    art = render_from_prompt(
        brief,
        out,
        ffmpeg=str(ffmpeg),
        quality=str(meta.get("quality") or "light"),
        studio="story",
    )
    slides = out / "slides"
    hashes = hash_png_dir(slides)
    probe = structural_probe(slides)
    expected_dir = golden_root() / demo_id / "expected"
    hashes_path = expected_dir / "hashes.json"
    manifest_path = expected_dir / "manifest.json"

    if update or not hashes_path.is_file():
        write_hashes_json(hashes_path, hashes, demo_id=demo_id, deterministic=True)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(probe, indent=2) + "\n", encoding="utf-8")
        ref = expected_dir / "slides"
        if ref.exists():
            shutil.rmtree(ref)
        if slides.is_dir():
            shutil.copytree(slides, ref)
        return DemoResult(
            demo_id=demo_id,
            kind="light_slideshow",
            passed=True,
            artifacts={**art, "slides": str(slides), "updated": True},
            notes="goldens refreshed",
        )

    expected = json.loads(hashes_path.read_text(encoding="utf-8"))
    exp_hashes = expected.get("hashes") or expected
    reports = [compare_hashes(hashes, exp_hashes)]
    if manifest_path.is_file():
        reports.append(
            compare_structural(
                probe, json.loads(manifest_path.read_text(encoding="utf-8"))
            )
        )
    passed = all(r.passed for r in reports)
    return DemoResult(
        demo_id=demo_id,
        kind="light_slideshow",
        passed=passed,
        reports=reports,
        artifacts={**art, "slides": str(slides)},
        notes="ok" if passed else "pixel/structural mismatch",
    )


def run_golden_demo(demo_id: str) -> dict[str, Any]:
    out = _ROOT / "out" / f"golden_{demo_id}"
    return run_demo(demo_id, out, update=False).to_dict()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Story golden demos")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--demo", default="story_light_beats")
    args = parser.parse_args(argv)
    out = _ROOT / "out" / f"golden_{args.demo}"
    result = run_demo(args.demo, out, update=args.refresh)
    print(json.dumps(result.to_dict(), indent=2, default=str))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
