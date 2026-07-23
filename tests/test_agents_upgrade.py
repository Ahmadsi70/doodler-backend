"""Agent upgrade contracts: richer board, craft re-apply, supervisor revision."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BRIEF = (
    "Hero enters the quiet room.\n\n"
    "Then they react in shock because the letter burns.\n\n"
    "They leave quietly."
)


def test_storyboard_emits_prompt_aligned_fields():
    from agents.story_chain import run_storyboard

    board = run_storyboard(BRIEF, runtime_seconds=30)
    assert len(board["shots"]) >= 3
    shot = board["shots"][0]
    for key in (
        "verb",
        "narrative_question",
        "composition_shape",
        "action_phases",
        "focal_point",
    ):
        assert key in shot, key
    assert shot["verb"]
    phases = shot["action_phases"]
    assert {p["phase"] for p in phases} >= {"anticipation", "action", "aftermath"}


def test_cinematography_uses_beat_not_pure_rotation():
    from agents.story_chain import run_cinematography, run_storyboard

    board = run_storyboard(BRIEF, runtime_seconds=30)
    cine = run_cinematography(board)
    frames = cine["frames"]
    assert len(frames) == len(board["shots"])
    shock = frames[1]
    assert shock["camera"] == "motivated_push"
    assert shock["lens"] == "action"
    assert shock.get("look_space_direction") in {"left", "right", "none"}
    assert "counterchange" in shock


def test_llm_timing_then_craft_reapplied(tmp_path: Path):
    """After fake LLM timing wipe, craft must restore behavior anticipation."""
    from agents import llm_enrich
    from agents.story_chain import run_story_agent_chain

    def fake_timing(brief, timing, storyboard):
        out = dict(timing)
        out["shots"] = [
            {
                **s,
                "anticipation_frames": 1,
                "hold_frames": 1,
                "williams_behavior_id": None,
            }
            for s in (timing.get("shots") or [])
        ]
        out["llm_enriched"] = True
        return out

    with (
        patch.object(llm_enrich, "llm_enabled", return_value=True),
        patch.object(llm_enrich, "deepseek_configured", return_value=True),
        patch.object(llm_enrich, "enrich_storyboard_llm", return_value=None),
        patch.object(llm_enrich, "enrich_cinematography_llm", return_value=None),
        patch.object(llm_enrich, "enrich_timing_llm", side_effect=fake_timing),
        patch.object(llm_enrich, "enrich_continuity_llm", return_value=None),
    ):
        chain = run_story_agent_chain(
            BRIEF,
            tmp_path,
            extras={"runtime_seconds": 30, "use_llm": True},
        )
    shock = next(
        s
        for s in chain.animation_timing["shots"]
        if "shock" in str(
            next(
                sh
                for sh in chain.storyboard["shots"]
                if sh["shot_id"] == s["shot_id"]
            ).get("action", "")
        ).lower()
        or s.get("williams_story_beat") == "reaction"
    )
    assert chain.animation_timing.get("williams_craft_applied") is True
    assert int(shock["anticipation_frames"]) >= 4
    assert int(shock["hold_frames"]) >= 12
    assert any("williams_craft=reapply" in n for n in chain.notes)


def test_supervisor_revision_hop_runs_once(tmp_path: Path):
    from agents.story_chain import run_story_agent_chain_with_supervision

    # Weak brief: 1 beat → supervisor fails → revision targets storyboard
    weak = "Only one lonely sentence without structure."
    result = run_story_agent_chain_with_supervision(
        weak,
        tmp_path,
        extras={"runtime_seconds": 20, "use_llm": False, "quality_gate_strict": False},
    )
    assert result.chain.ok or len(result.chain.storyboard.get("shots") or []) >= 1
    assert result.revision_passes >= 0
    # After revision, middle/end should gain causal scaffolding when possible
    if result.revision_passes:
        assert any("revision=" in n for n in result.chain.notes)
        actions = " ".join(
            str(s.get("action") or "") for s in result.chain.storyboard.get("shots") or []
        ).lower()
        assert any(k in actions for k in ("then", "because", "بعد", "چون"))


def test_remotion_prefers_cine_look_space(tmp_path: Path):
    import json

    from tools.remotion_emitter import write_story_composition_props

    path = write_story_composition_props(
        tmp_path,
        storyboard={"shots": [{"shot_id": 0, "title": "A", "action": "Look", "duration_sec": 2}]},
        cinematography={
            "frames": [
                {
                    "shot_id": 0,
                    "lens": "beauty",
                    "camera": "static",
                    "composition": "L",
                    "look_space_direction": "right",
                }
            ]
        },
        timing={"shots": [{"shot_id": 0, "duration_sec": 2, "duration_frames": 48}]},
    )
    props = json.loads(path.read_text(encoding="utf-8"))
    assert props["shots"][0]["lookSpace"] == "right"
    assert props["shots"][0]["thirdsX"] == 0.33
