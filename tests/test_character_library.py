"""Character library — persistent profiles across films."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _png(path: Path, color=(40, 120, 200)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), color).save(path)


def test_create_list_get_character(tmp_path: Path, monkeypatch):
    from tools import character_library as lib

    monkeypatch.setattr(lib, "default_library_root", lambda: tmp_path / "characters")
    portrait = tmp_path / "hero.png"
    _png(portrait)
    profile = lib.create_character(
        name_fa="لیلا",
        appearance_fa="موی تیره، لباس آبی",
        portrait_path=portrait,
        character_id="leila_v1",
    )
    assert profile["id"] == "leila_v1"
    assert profile["name_fa"] == "لیلا"
    assert (tmp_path / "characters" / "leila_v1" / "portrait.png").is_file()
    assert (tmp_path / "characters" / "leila_v1" / "profile.json").is_file()

    listed = lib.list_characters()
    assert any(c["id"] == "leila_v1" for c in listed)

    got = lib.get_character("leila_v1")
    assert got is not None
    assert got["appearance_fa"].startswith("موی")


def test_resolve_character_paths(tmp_path: Path, monkeypatch):
    from tools import character_library as lib

    monkeypatch.setattr(lib, "default_library_root", lambda: tmp_path / "characters")
    portrait = tmp_path / "p.png"
    body = tmp_path / "body.png"
    _png(portrait)
    _png(body, (10, 10, 10))
    lib.create_character(
        name_fa="قهرمان",
        appearance_fa="ردای قرمز",
        portrait_path=portrait,
        layers={"body": str(body)},
        character_id="hero_a",
    )
    resolved = lib.resolve_character("hero_a")
    assert resolved["character_path"].endswith("portrait.png")
    assert Path(resolved["character_path"]).is_file()
    assert resolved["layers"]["body"]
    assert Path(resolved["layers"]["body"]).is_file()
    assert resolved["appearance_fa"] == "ردای قرمز"


def test_studio_spec_resolves_character_id(tmp_path: Path, monkeypatch):
    from studio_spec import ShotControl, StudioSpec
    from tools import character_library as lib

    monkeypatch.setattr(lib, "default_library_root", lambda: tmp_path / "characters")
    portrait = tmp_path / "c.png"
    _png(portrait)
    lib.create_character(
        name_fa="لیلا",
        appearance_fa="چهره ملایم",
        portrait_path=portrait,
        character_id="leila_v1",
    )
    spec = StudioSpec(
        title="فانوس",
        character_id="leila_v1",
        shots=[
            ShotControl(
                action="وارد می‌شود",
                duration_sec=3,
                story_beat="entrance",
            )
        ],
    )
    path = spec.resolved_character()
    assert path and Path(path).is_file()
    assert "leila_v1" in path.replace("\\", "/")


def test_apply_character_copies_into_job(tmp_path: Path, monkeypatch):
    from tools import character_library as lib

    monkeypatch.setattr(lib, "default_library_root", lambda: tmp_path / "characters")
    portrait = tmp_path / "c.png"
    _png(portrait)
    lib.create_character(
        name_fa="لیلا",
        appearance_fa="آبی",
        portrait_path=portrait,
        character_id="leila_v1",
    )
    job = tmp_path / "job1"
    out = lib.materialize_character_into_job("leila_v1", job)
    assert Path(out["character_path"]).is_file()
    assert "assets" in str(out["character_path"]).replace("\\", "/")
    assert str(job.resolve()) in str(Path(out["character_path"]).resolve())


def test_image_needs_includes_appearance_when_provided():
    from agents.image_needs_agent import run_image_needs_agent
    from studio_spec import ShotControl, StudioSpec

    spec = StudioSpec(
        title="t",
        shots=[
            ShotControl(action="می‌خندد", duration_sec=3, story_beat="reaction")
        ],
    )
    needs = run_image_needs_agent(
        spec,
        character_appearance_fa="موی تیره، لباس آبی پاستلی",
    )
    ref = next(a for a in needs["assets"] if a["kind"] == "character_ref")
    assert "موی تیره" in ref["screenplay_anchor"] or "موی تیره" in str(
        ref.get("appearance_fa") or ""
    )
