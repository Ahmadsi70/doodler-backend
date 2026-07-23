"""Portable story packs: share Spec + swap character assets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fake_png(path: Path, color: tuple[int, int, int] = (200, 80, 80)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 96), color).save(path)
    return path


def test_export_pack_uses_relative_asset_paths(tmp_path: Path):
    from studio_spec import ShotControl, StudioSpec
    from tools.story_pack import export_story_pack, load_pack_spec

    hero = _fake_png(tmp_path / "hero.png")
    spec = StudioSpec(
        title="Shareable",
        quality="light",
        mode="direct",
        character_path=str(hero),
        shots=[
            ShotControl(action="Enter", duration_sec=2, story_beat="entrance", pose="walk"),
            ShotControl(
                action="Then react because fire",
                duration_sec=2.5,
                story_beat="reaction",
                pose="react",
                expression="shock",
            ),
        ],
    )
    pack_dir = export_story_pack(spec, tmp_path / "pack_out", pack_id="demo_pack")
    assert (pack_dir / "studio_spec.json").is_file()
    assert (pack_dir / "pack.json").is_file()
    assert (pack_dir / "README.md").is_file()
    assert (pack_dir / "assets" / "character.png").is_file()

    packed = json.loads((pack_dir / "studio_spec.json").read_text(encoding="utf-8"))
    assert packed["character_path"] == "assets/character.png"
    assert packed["assets"]["character_path"] == "assets/character.png"

    loaded = load_pack_spec(pack_dir)
    assert loaded.resolved_character()
    assert Path(loaded.resolved_character()).is_file()


def test_swap_character_in_pack(tmp_path: Path):
    from studio_spec import ShotControl, StudioSpec
    from tools.story_pack import export_story_pack, swap_pack_character, load_pack_spec

    a = _fake_png(tmp_path / "a.png", (10, 20, 30))
    b = _fake_png(tmp_path / "b.png", (90, 100, 110))
    spec = StudioSpec(
        title="Swap",
        mode="direct",
        character_path=str(a),
        shots=[ShotControl(action="Hi", duration_sec=2, story_beat="entrance")],
    )
    pack = export_story_pack(spec, tmp_path / "pack", pack_id="swap")
    swap_pack_character(pack, b)
    loaded = load_pack_spec(pack)
    # file replaced; path still relative assets/character.png
    assert Path(loaded.resolved_character()).read_bytes() == b.read_bytes()
