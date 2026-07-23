"""Export-only bundle: screenplay, prompts, engine code — no in-tool render."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio_spec import ShotControl, StudioSpec


def _mini_spec() -> StudioSpec:
    return StudioSpec(
        title="آزمون",
        mode="direct",
        runtime_seconds=12,
        shots=[
            ShotControl(
                title="ورود",
                action="قهرمان وارد سالن می‌شود.",
                duration_sec=3,
                pose="walk",
                story_beat="entrance",
                dialogue="سلام.",
            ),
            ShotControl(
                title="شوک",
                action="بعد با شوک واکنش نشان می‌دهد چون نامه می‌سوزد.",
                duration_sec=4,
                pose="react",
                expression="shock",
                camera="motivated_push",
                story_beat="reaction",
            ),
        ],
    )


def test_export_bundle_writes_screenplay_and_manifest(tmp_path):
    from tools.animation_export import export_animation_bundle

    spec = _mini_spec()
    out = export_animation_bundle(spec, tmp_path / "bundle", targets=["prompts"])
    root = Path(out["export_root"])
    assert out["ok"] is True
    assert (root / "manifest.json").is_file()
    assert (root / "studio_spec.json").is_file()
    assert (root / "screenplay.md").is_file()
    assert (root / "explanation.md").is_file()
    text = (root / "screenplay.md").read_text(encoding="utf-8")
    assert "قهرمان" in text
    assert "صحنه" in text or "نمایشنامه" in text
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["title"] == "آزمون"
    assert manifest["targets"] == ["prompts"]


def test_export_prompts_per_shot(tmp_path):
    from tools.animation_export import export_animation_bundle

    root = Path(
        export_animation_bundle(
            _mini_spec(), tmp_path / "b", targets=["prompts"]
        )["export_root"]
    )
    p0 = root / "prompts" / "shot_00.txt"
    assert p0.is_file()
    assert "walk" in p0.read_text(encoding="utf-8").lower() or "قدم" in p0.read_text(
        encoding="utf-8"
    )


def test_export_remotion_engine_code_without_mp4(tmp_path):
    from tools.animation_export import export_animation_bundle

    result = export_animation_bundle(
        _mini_spec(), tmp_path / "b", targets=["remotion"]
    )
    root = Path(result["export_root"])
    props = root / "engines" / "remotion" / "story_props.json"
    guide = root / "engines" / "remotion" / "guide.md"
    assert props.is_file()
    assert guide.is_file()
    assert not (root / "render.mp4").is_file()
    data = json.loads(props.read_text(encoding="utf-8"))
    assert data["fps"] == 24
    assert len(data["shots"]) == 2


def test_export_slideshow_engine_snippet(tmp_path):
    from tools.animation_export import export_animation_bundle

    root = Path(
        export_animation_bundle(
            _mini_spec(), tmp_path / "b", targets=["slideshow"]
        )["export_root"]
    )
    script = root / "engines" / "slideshow" / "build.py"
    guide = root / "engines" / "slideshow" / "guide.md"
    assert script.is_file()
    assert guide.is_file()
    assert "render_from_prompt" in script.read_text(encoding="utf-8")


def test_export_from_spec_cli_shape(tmp_path):
    from tools.studio_api import export_from_spec

    result = export_from_spec(_mini_spec(), workspace=tmp_path / "job")
    assert result["ok"] is True
    assert "export_root" in (result.get("artifacts") or {})
    assert not (tmp_path / "job" / "render.mp4").exists()
