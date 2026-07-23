"""AudioCueAgent — constrained selection from Kenney catalog."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_catalog_has_at_least_100_kenney_cues():
    from agents.audio_cue_agent import load_audio_catalog

    cat = load_audio_catalog()
    kenney = [
        k
        for k, v in (cat.get("cues") or {}).items()
        if "kenney" in (v.get("tags") or []) or str(v.get("attribution") or "").lower().startswith("kenney")
    ]
    # aliases may dilute; count files
    files = list((ROOT / "libraries" / "audio" / "files").glob("foley_*.wav"))
    assert len(files) >= 100
    assert len(cat.get("cues") or {}) >= 100


def test_audio_cue_agent_picks_from_catalog_only():
    from agents.audio_cue_agent import run_audio_cue_agent

    shots = [
        {
            "shot_id": 0,
            "action": "Hero walks into the hall.",
            "story_beat": "entrance",
            "duration_frames": 48,
        },
        {
            "shot_id": 1,
            "action": "Then shock because the letter burns.",
            "story_beat": "reaction",
            "duration_frames": 36,
        },
        {
            "shot_id": 2,
            "action": "Fight breaks out in the corridor.",
            "story_beat": "conflict",
            "duration_frames": 48,
        },
    ]
    out = run_audio_cue_agent(shots, fps=24, emotion="tense")
    assert out["agent"] == "AudioCueAgent"
    assert out["schema"] == "audio_cue_plan#v1"
    assert len(out["events"]) >= 3
    catalog_ids = set(json.loads((ROOT / "libraries/audio/catalog.json").read_text(encoding="utf-8"))["cues"])
    for ev in out["events"]:
        assert ev["cue"] in catalog_ids
        assert ev["file"].startswith("audio/") or ev["file"].startswith("files/")


def test_audio_cue_agent_entrance_prefers_footstep():
    from agents.audio_cue_agent import run_audio_cue_agent

    out = run_audio_cue_agent(
        [{"shot_id": 0, "action": "Walks in.", "story_beat": "entrance", "duration_frames": 24}],
        fps=24,
    )
    cues = [e["cue"] for e in out["events"] if e.get("role") != "bed"]
    assert any("footstep" in c for c in cues)


def test_timeline_builder_uses_agent_plan(tmp_path: Path):
    from tools.audio_cues import build_audio_timeline_from_plan
    from agents.audio_cue_agent import run_audio_cue_agent

    shots = [
        {"shotId": 0, "storyBeat": "entrance", "durationFrames": 24, "action": "Enter."},
        {"shotId": 1, "storyBeat": "reaction", "durationFrames": 24, "action": "Shock."},
    ]
    plan = run_audio_cue_agent(
        [
            {"shot_id": 0, "story_beat": "entrance", "duration_frames": 24, "action": "Enter."},
            {"shot_id": 1, "story_beat": "reaction", "duration_frames": 24, "action": "Shock."},
        ],
        fps=24,
    )
    tl = build_audio_timeline_from_plan(plan, shots, fps=24)
    assert tl["schema"] == "audio_timeline#v1"
    assert tl["events"]
    assert tl.get("agent") == "AudioCueAgent"
