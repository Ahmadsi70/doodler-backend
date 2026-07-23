"""LiteraryScreenplayAgent + StyleRecommenderAgent tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio_spec import ShotControl, StudioSpec


def _spec() -> StudioSpec:
    return StudioSpec(
        title="نامهٔ سحر",
        style_id="ink_bw_editorial",
        grade="bw_graphic",
        emotion="sad",
        runtime_seconds=50,
        shots=[
            ShotControl(
                title="ورود مه‌آلود",
                action="پسرک با کوله وارد ایستگاه متروکه می‌شود؛ مه روی ریل‌ها می‌نشیند.",
                duration_sec=10,
                pose="walk",
                story_beat="entrance",
                camera="pan_follow",
                shot_size="WS",
                lighting="three_point",
            ),
            ShotControl(
                title="نور مرموز",
                action="از داخل واگن قدیمی نور ضعیف می‌درخشد.",
                duration_sec=8,
                pose="idle",
                story_beat="reveal",
                camera="reveal_drift",
                shot_size="MS",
            ),
            ShotControl(
                title="کشف",
                action="جعبه را باز می‌کند؛ نامه و عکس سیاه‌سفید داخلش است.",
                duration_sec=12,
                pose="react",
                expression="sad",
                story_beat="reaction",
                camera="motivated_push",
                shot_size="CU",
                dialogue="(VO) «این نامه… برای من نبود.»",
            ),
        ],
    )


def _compiled_like(spec: StudioSpec):
    from tools.studio_api import compile_studio_spec

    return compile_studio_spec(spec)


def test_literary_screenplay_has_slugline_and_camera():
    from agents.literary_screenplay_agent import run_literary_screenplay_agent

    compiled = _compiled_like(_spec())
    out = run_literary_screenplay_agent(
        _spec(),
        storyboard=compiled.storyboard,
        cinematography=compiled.cinematography,
        continuity=compiled.continuity,
    )
    md = out["screenplay_md"]
    assert "INT." in md or "EXT." in md
    assert "دوربین" in md or "CAMERA" in md.upper()
    assert "نور" in md or "lighting" in md.lower()
    assert len(out["shots"]) == 3
    assert out["shots"][0].get("slugline")


def test_literary_includes_vo_and_subtext():
    from agents.literary_screenplay_agent import run_literary_screenplay_agent

    compiled = _compiled_like(_spec())
    out = run_literary_screenplay_agent(
        _spec(),
        storyboard=compiled.storyboard,
        cinematography=compiled.cinematography,
    )
    md = out["screenplay_md"]
    assert "VO" in md or "دیالوگ" in md
    assert "نامه" in md


def test_style_recommender_for_misty_station_brief():
    from agents.style_recommender_agent import recommend_styles

    brief = (
        "سحرگاه مه روی ایستگاه متروکه. "
        "نور مرموز از واگن. نامه و عکس سیاه‌سفید. غم آرام."
    )
    out = recommend_styles(brief, emotion="sad")
    assert out["primary_style_id"]
    assert len(out["alternatives"]) >= 1
    assert out["primary_style_id"] in {
        "ink_bw_editorial",
        "moody_portrait_brand",
        "surreal_dream_cut",
        "epic_wide_myth",
    }
    assert out["rationale_fa"]


def test_screenplay_agent_uses_literary_when_cine_provided():
    from agents.screenplay_agent import run_screenplay_agent

    compiled = _compiled_like(_spec())
    out = run_screenplay_agent(
        _spec(),
        storyboard=compiled.storyboard,
        cinematography=compiled.cinematography,
        continuity=compiled.continuity,
    )
    assert out.get("literary") is True
    assert "INT." in out["screenplay_md"] or "EXT." in out["screenplay_md"]


def test_export_bundle_includes_style_recommendation(tmp_path):
    from tools.animation_export import export_animation_bundle

    spec = _spec()
    spec = spec.model_copy(update={"notes": spec.to_brief()})
    root = Path(
        export_animation_bundle(spec, tmp_path / "b", targets=["prompts"])["export_root"]
    )
    rec = root / "style_recommendation.json"
    assert rec.is_file()
    assert "primary_style_id" in rec.read_text(encoding="utf-8")
