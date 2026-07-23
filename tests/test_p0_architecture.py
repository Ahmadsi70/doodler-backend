"""P0 architecture: acts, context pack, performance bible, continuity graph, props contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _spec_many(n: int = 12):
    from studio_spec import ShotControl, StudioSpec

    shots = []
    for i in range(n):
        beat = ["entrance", "reveal", "reaction", "conflict", "decision", "exit"][i % 6]
        pose = ["walk", "idle", "react", "run"][i % 4]
        shots.append(
            ShotControl(
                action=f"Beat {i} happens because stakes rise.",
                title=f"S{i}",
                duration_sec=2.5,
                story_beat=beat,  # type: ignore[arg-type]
                pose=pose,  # type: ignore[arg-type]
                composition="L" if i % 2 == 0 else "R",
                camera="motivated_push" if i % 3 == 0 else "static",
            )
        )
    return StudioSpec(
        title="LongForm",
        runtime_seconds=min(600, n * 2.5),
        mode="direct",
        shots=shots,
    )


def test_act_planner_splits_long_runtime():
    from tools.act_planner import plan_acts

    plan = plan_acts(_spec_many(12), target_act_seconds=10.0)
    assert len(plan.acts) >= 2
    assert plan.acts[0].shot_start == 0
    assert plan.acts[-1].shot_end == 12
    # Contiguous coverage
    for a, b in zip(plan.acts, plan.acts[1:]):
        assert a.shot_end == b.shot_start
    total = sum(a.duration_sec for a in plan.acts)
    assert abs(total - 12 * 2.5) < 0.01


def test_context_pack_respects_budget_and_layers():
    from tools.act_planner import plan_acts
    from tools.context_pack import build_compressed_context

    spec = _spec_many(9)
    plan = plan_acts(spec, target_act_seconds=8.0)
    act = plan.acts[0]
    pack = build_compressed_context(
        spec,
        act=act,
        bible="Hero seeks truth. Tone: quiet dread.",
        token_budget=2000,
    )
    assert pack.token_budget == 2000
    assert pack.token_used <= 2000
    names = [layer.name for layer in pack.layers]
    assert names == ["essential", "relevant", "summary", "collaboration"]
    assert any(layer.content for layer in pack.layers)
    # Must not dump entire film into essential
    essential = pack.layers[0].content
    assert "Beat 8" not in essential or act.shot_end > 8


def test_scene_ir_includes_compressed_context(tmp_path: Path):
    from tools.act_planner import plan_acts
    from tools.context_pack import build_compressed_context
    from tools.scene_ir_builder import build_scene_ir_from_chain
    from tools.studio_api import compile_studio_spec

    spec = _spec_many(6)
    compiled = compile_studio_spec(spec)
    plan = plan_acts(spec, target_act_seconds=20.0)
    pack = build_compressed_context(spec, act=plan.acts[0], bible=spec.title)
    ir = build_scene_ir_from_chain(
        spec.to_brief(),
        storyboard=compiled.storyboard,
        cinematography=compiled.cinematography,
        timing=compiled.timing,
        continuity=compiled.continuity,
        job_id="t",
        job_out_dir=str(tmp_path),
        runtime_seconds=spec.runtime_seconds,
        compressed_context=pack,
        act_plan=plan.to_public_dict(),
    )
    assert ir.compressed_context is not None
    assert ir.compressed_context.token_used > 0
    assert any("act_plan" in n for n in ir.notes)


def test_performance_bible_drives_walk_cycle():
    from tools.pose_presets import bake_shot_rig, joints_for_pose, load_performance_bible

    bible = load_performance_bible()
    assert "walk" in bible["poses"]
    walk = joints_for_pose("walk", "neutral")
    assert walk["leftLegStride"] != 0
    rig = bake_shot_rig(pose="walk", expression="neutral", fps=24)
    assert len(rig["keyframes"]) >= 3
    assert rig.get("performance_id") == "walk"


def test_continuity_graph_screen_direction_and_states():
    from tools.continuity_graph import build_continuity_graph
    from tools.studio_api import compile_studio_spec

    spec = _spec_many(4)
    compiled = compile_studio_spec(spec)
    graph = build_continuity_graph(
        storyboard=compiled.storyboard,
        cinematography=compiled.cinematography,
        continuity=compiled.continuity,
    )
    assert graph["schema"] == "continuity_graph#v1"
    assert len(graph["nodes"]) == 4
    assert "edges" in graph
    assert graph["nodes"][0]["screen_direction"] in {"L_to_R", "R_to_L", "hold"}
    assert "emotion" in graph["nodes"][0]["state"]


def test_props_contract_includes_graph_transition_caption(tmp_path: Path):
    from tools.continuity_graph import build_continuity_graph
    from tools.remotion_emitter import write_story_composition_props
    from tools.studio_api import compile_studio_spec

    spec = _spec_many(3)
    compiled = compile_studio_spec(spec)
    graph = build_continuity_graph(
        storyboard=compiled.storyboard,
        cinematography=compiled.cinematography,
        continuity=compiled.continuity,
    )
    cont = {**compiled.continuity, "graph": graph}
    path = write_story_composition_props(
        tmp_path,
        storyboard=compiled.storyboard,
        cinematography=compiled.cinematography,
        timing=compiled.timing,
        continuity=cont,
        style_profile={
            "style_id": "symmetrical_pastel_cinema",
            "engine": {"grade": "pastel_muted", "pace": "measured"},
        },
        title=spec.title,
    )
    props = json.loads(path.read_text(encoding="utf-8"))
    assert props["visualVersion"] >= 3
    assert "graph" in props["continuity"]
    shot0 = props["shots"][0]
    assert "captionMode" in shot0
    assert shot0["captionMode"] == "lower_third"
    assert "transitionIn" in shot0
    assert "cameraMove" in shot0
    assert shot0.get("shotRig")
    assert shot0.get("envProfile")


def test_craft_pack_loaders_exist():
    from tools.craft_packs import load_audio_cues, load_cine_lexicon, load_look_bible, load_transition_grammar

    assert load_cine_lexicon()["shots"]
    assert load_look_bible()["grades"]
    assert load_transition_grammar()["transitions"]
    assert load_audio_cues()["cues"]


def test_act_chunks_for_render():
    from tools.act_planner import chunk_spec_by_acts, plan_acts

    spec = _spec_many(9)
    plan = plan_acts(spec, target_act_seconds=8.0)
    chunks = chunk_spec_by_acts(spec, plan)
    assert len(chunks) == len(plan.acts)
    assert sum(len(c.shots) for c in chunks) == len(spec.shots)
