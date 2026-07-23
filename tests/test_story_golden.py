"""Story Light golden — pixel hash + structural probe."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.golden_demos import golden_root, list_demos, load_demo_meta, run_demo
from tools.pixel_qa import compare_hashes, structural_probe
from tools.studio_profiles import find_ffmpeg

UPDATE = os.environ.get("UPDATE_GOLDENS", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def test_story_golden_fixture_exists():
    assert "story_light_beats" in list_demos()
    meta = load_demo_meta("story_light_beats")
    assert meta.get("studio") == "story"
    assert (golden_root() / "story_light_beats").is_dir()


def test_compare_hashes_detects_mismatch():
    r = compare_hashes({"slide_000.png": "aaa"}, {"slide_000.png": "bbb"})
    assert r.passed is False


@pytest.mark.skipif(not find_ffmpeg(), reason="ffmpeg required")
def test_story_light_pixel_golden(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ANIMATION_DETERMINISTIC_SLIDES", "1")
    demo_id = "story_light_beats"
    result = run_demo(demo_id, tmp_path / demo_id, update=UPDATE)
    assert result.passed, (
        f"{demo_id} failed: {result.notes} "
        f"reports={[r.to_dict() for r in result.reports]}"
    )
    slides = Path(result.artifacts["slides"])
    probe = structural_probe(slides)
    assert probe["slide_count"] >= 3
    accent = probe["accent_rgb_first"]
    # Story pastel blue accent: B >= R
    assert accent[2] >= accent[0]
