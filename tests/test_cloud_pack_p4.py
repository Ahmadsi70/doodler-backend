"""P4 — character in remotion export + ZIP download pack."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio_spec import ShotControl, StudioSpec


def _png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48, 48), (20, 90, 160)).save(path)


def _spec_with_char(tmp_path: Path, monkeypatch) -> StudioSpec:
    from tools import character_library as lib

    monkeypatch.setattr(lib, "default_library_root", lambda: tmp_path / "characters")
    portrait = tmp_path / "hero.png"
    _png(portrait)
    lib.create_character(
        name_fa="لیلا",
        appearance_fa="موی تیره، لباس آبی پاستلی",
        portrait_path=portrait,
        character_id="leila_v1",
    )
    return StudioSpec(
        title="فانوس",
        character_id="leila_v1",
        runtime_seconds=12,
        shots=[
            ShotControl(
                action="لیلا وارد اتاق می‌شود و می‌خندد.",
                duration_sec=4,
                story_beat="entrance",
                pose="walk",
            ),
            ShotControl(
                action="فانوس روشن می‌شود.",
                duration_sec=4,
                story_beat="reveal",
            ),
        ],
    )


def test_export_remotion_copies_library_character(tmp_path: Path, monkeypatch):
    from tools.animation_export import export_animation_bundle

    spec = _spec_with_char(tmp_path, monkeypatch)
    out = export_animation_bundle(spec, tmp_path / "ex", targets=["remotion", "prompts"])
    root = Path(out["export_root"])
    char = root / "engines" / "remotion" / "assets" / "character.png"
    assert char.is_file()
    assert (root / "assets" / "character" / "portrait.png").is_file() or char.is_file()
    props = json.loads(
        (root / "engines" / "remotion" / "story_props.json").read_text(encoding="utf-8")
    )
    assert "shots" in props or "characterPath" in props
    guide = (root / "engines" / "remotion" / "CLOUD_RENDER.md").read_text(encoding="utf-8")
    assert "remotion render" in guide.lower() or "npx remotion" in guide


def test_prompt_craft_locks_appearance_on_keyframes(tmp_path: Path, monkeypatch):
    from agents.prompt_craft_agent import run_prompt_craft_agent

    spec = _spec_with_char(tmp_path, monkeypatch)
    out = run_prompt_craft_agent(spec)
    assert out["version"] == "2"
    ref = next(a for a in out["assets"] if a["kind"] == "character_ref")
    assert "موی تیره" in ref["prompt"] or "آبی" in ref["prompt"]
    key = next(a for a in out["assets"] if a["kind"] == "keyframe")
    assert "موی تیره" in key["prompt"] or "آبی" in key["prompt"] or "لیلا" in key["prompt"]
    assert "موی تیره" in out["film_prompt"] or "آبی" in out["film_prompt"]


def test_zip_cloud_pack_contains_remotion_scaffold(tmp_path: Path, monkeypatch):
    from tools.cloud_pack import build_cloud_render_zip
    from tools.animation_export import export_animation_bundle

    spec = _spec_with_char(tmp_path, monkeypatch)
    export_root = Path(
        export_animation_bundle(spec, tmp_path / "ex", targets=["remotion", "prompts"])[
            "export_root"
        ]
    )
    zip_path = build_cloud_render_zip(export_root, tmp_path / "film_cloud.zip")
    assert zip_path.is_file()
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
    assert any("story_props.json" in n for n in names)
    assert any(n.endswith("package.json") for n in names)
    assert any("StoryNarrative" in n or "src/" in n for n in names)
    assert any("character.png" in n or "portrait.png" in n for n in names)
    assert any("CLOUD_RENDER.md" in n for n in names)
