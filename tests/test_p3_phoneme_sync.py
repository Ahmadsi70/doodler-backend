"""P3: PhonemeSyncAgent — VO lip-sync with visual lead ≤2 frames."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_phoneme_sync_empty_without_vo():
    from agents.phoneme_sync_agent import run_phoneme_sync_agent

    out = run_phoneme_sync_agent(
        [{"shot_id": 0, "action": "Hero walks in.", "duration_frames": 48}],
        fps=24,
    )
    assert out["agent"] == "PhonemeSyncAgent"
    assert out["schema"] == "phoneme_sync#v1"
    assert out["phonemes"] == []
    assert out["active"] is False


def test_phoneme_sync_from_dialogue_with_visual_lead():
    from agents.phoneme_sync_agent import run_phoneme_sync_agent

    shots = [
        {
            "shot_id": 0,
            "action": "Hero speaks.",
            "dialogue": "Oh no!",
            "duration_frames": 48,
            "anticipation_frames": 6,
        }
    ]
    out = run_phoneme_sync_agent(shots, fps=24, lead_frames=2)
    assert out["active"] is True
    assert out["phonemes"]
    for p in out["phonemes"]:
        assert p["visual_frame"] <= p["audio_frame"]
        assert p["audio_frame"] - p["visual_frame"] <= 2
        assert p["lead_frames"] in {1, 2}
        assert p["shape"]
        assert 0 <= p["audio_frame"] < 48
    # rest at end
    assert any(p["shape"] == "rest" for p in out["phonemes"])


def test_phoneme_sync_from_quoted_action():
    from agents.phoneme_sync_agent import run_phoneme_sync_agent

    out = run_phoneme_sync_agent(
        [
            {
                "shot_id": 1,
                "action": 'She says "Hello there" softly.',
                "duration_frames": 36,
            }
        ],
        fps=24,
    )
    assert out["active"] is True
    tokens = [p["token"] for p in out["phonemes"] if p["shape"] != "rest"]
    assert tokens


def test_phoneme_mouth_curve_merges_into_expression():
    from agents.phoneme_sync_agent import (
        mouth_curve_for_shot,
        run_phoneme_sync_agent,
    )

    shots = [
        {
            "shot_id": 0,
            "dialogue": "Hi",
            "duration_frames": 24,
            "anticipation_frames": 4,
        }
    ]
    sync = run_phoneme_sync_agent(shots, fps=24, lead_frames=2)
    curve = mouth_curve_for_shot(sync, 0)
    assert curve
    assert curve[0]["frame"] == 0
    mouths = [c["mouth"] for c in curve]
    assert max(mouths) > min(mouths)


def test_props_include_phoneme_sync_when_dialogue(tmp_path: Path):
    from studio_spec import ShotControl, StudioSpec
    from tools.remotion_emitter import write_story_composition_props
    from tools.studio_api import compile_studio_spec

    spec = StudioSpec(
        title="P3",
        shots=[
            ShotControl(
                action="Hero speaks a warning.",
                dialogue="Oh no fire!",
                story_beat="reaction",
                pose="react",
                expression="shock",
                duration_sec=2,
            ),
        ],
    )
    c = compile_studio_spec(spec)
    path = write_story_composition_props(
        tmp_path,
        storyboard=c.storyboard,
        cinematography=c.cinematography,
        timing=c.timing,
        continuity=c.continuity,
        title=spec.title,
    )
    props = json.loads(path.read_text(encoding="utf-8"))
    assert props.get("phonemeSync")
    assert props["phonemeSync"]["active"] is True
    assert props["phonemeSync"]["phonemes"]
    # expressionCurve mouth driven by visemes
    ec = props["shots"][0].get("expressionCurve") or []
    assert any("mouth" in k for k in ec)
