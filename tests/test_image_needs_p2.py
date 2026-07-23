"""P2 — ImageNeedsAgent + screenplay-grounded PromptCraft."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio_spec import ShotControl, StudioSpec


def _spec() -> StudioSpec:
    return StudioSpec(
        title="فانوس",
        style_id="symmetrical_pastel_cinema",
        grade="pastel_muted",
        emotion="happy",
        runtime_seconds=24,
        character_path=None,
        shots=[
            ShotControl(
                title="ورود",
                action="لیلا وارد اتاق نقاشی با پنجرهٔ گرد می‌شود.",
                duration_sec=6,
                pose="walk",
                story_beat="entrance",
                camera="static",
                shot_size="WS",
                composition="C",
            ),
            ShotControl(
                title="قلم‌مو",
                action="قلم‌مو آبی را از جعبه برمی‌دارد.",
                duration_sec=5,
                pose="react",
                story_beat="reveal",
                camera="motivated_push",
                shot_size="CU",
                composition="C",
            ),
            ShotControl(
                title="فانوس",
                action="فانوس روی بوم روشن می‌شود.",
                duration_sec=7,
                pose="idle",
                expression="happy",
                story_beat="decision",
                camera="static",
                shot_size="MS",
                composition="C",
            ),
        ],
    )


def _screenplay() -> dict:
    return {
        "screenplay_md": "# فانوس\n\n## صحنه 1\nلیلا وارد اتاق نقاشی می‌شود.\n",
        "scenes": [
            {"index": 0, "action": "لیلا وارد اتاق نقاشی با پنجرهٔ گرد می‌شود."},
            {"index": 1, "action": "قلم‌مو آبی را از جعبه برمی‌دارد."},
            {"index": 2, "action": "فانوس روی بوم روشن می‌شود."},
        ],
    }


def _storyboard() -> dict:
    return {
        "shots": [
            {
                "shot_id": 0,
                "verb": "enter",
                "focal_point": "window",
                "composition_shape": "center",
            },
            {
                "shot_id": 1,
                "verb": "reach",
                "focal_point": "brush",
                "composition_shape": "close",
            },
            {
                "shot_id": 2,
                "verb": "glow",
                "focal_point": "lantern",
                "composition_shape": "center",
            },
        ]
    }


def test_image_needs_lists_assets_per_shot_and_kinds():
    from agents.image_needs_agent import run_image_needs_agent

    needs = run_image_needs_agent(
        _spec(),
        screenplay=_screenplay(),
        storyboard=_storyboard(),
    )
    assert needs["agent"] == "ImageNeedsAgent"
    assert needs["version"] == "1"
    kinds = {a["kind"] for a in needs["assets"]}
    assert "keyframe" in kinds
    assert "character_ref" in kinds
    assert any(a["kind"] == "establishing" for a in needs["assets"])
    assert any(a["kind"] == "insert" for a in needs["assets"])
    keyframes = [a for a in needs["assets"] if a["kind"] == "keyframe"]
    assert len(keyframes) == 3
    for a in needs["assets"]:
        assert a["asset_id"]
        assert "framing" in a
        assert a["framing"]["aspect"] == "16:9"
        assert a["framing"].get("crop_note_fa")
        assert a.get("timeline_slot")
        assert a.get("screenplay_anchor")


def test_prompt_craft_grounds_in_screenplay_and_needs():
    from agents.image_needs_agent import run_image_needs_agent
    from agents.prompt_craft_agent import run_prompt_craft_agent
    from tools.studio_api import compile_studio_spec

    spec = _spec()
    compiled = compile_studio_spec(spec)
    needs = run_image_needs_agent(
        spec, screenplay=_screenplay(), storyboard=_storyboard()
    )
    out = run_prompt_craft_agent(
        spec,
        cinematography=compiled.cinematography,
        continuity=compiled.continuity,
        screenplay=_screenplay(),
        storyboard=_storyboard(),
        image_needs=needs,
    )
    assert out["version"] == "2"
    assert out.get("image_needs")
    assert len(out["assets"]) >= 3
    asset0 = next(a for a in out["assets"] if a["kind"] == "keyframe" and a["shot_id"] == 0)
    assert "لیلا" in asset0["prompt"] or "اتاق" in asset0["prompt"]
    assert "16:9" in asset0["prompt"]
    assert "focal" in asset0["prompt"].lower() or "پنجره" in asset0["prompt"] or "window" in asset0["prompt"].lower()
    # backward-compat shot files
    assert len(out["shots"]) == 3
    assert out["shots"][0]["id"] == "shot_00"
    assert "لیلا" in out["shots"][0]["prompt"] or "اتاق" in out["shots"][0]["prompt"]


def test_export_writes_image_manifest(tmp_path: Path):
    from tools.animation_export import export_animation_bundle

    root = Path(
        export_animation_bundle(_spec(), tmp_path / "ex", targets=["prompts"])["export_root"]
    )
    man = root / "prompts" / "image_manifest.json"
    assert man.is_file()
    data = json.loads(man.read_text(encoding="utf-8"))
    assert data.get("assets")
    assert any(a.get("kind") == "keyframe" for a in data["assets"])
    assert (root / "prompts" / "assets").is_dir() or any(
        (root / "prompts").glob("asset_*.txt")
    ) or (root / "prompts" / "shot_00.txt").is_file()
