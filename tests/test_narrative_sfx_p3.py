"""P3 narrative SFX — schema in breakdown/screenplay, catalog gaps, Persian keywords."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio_spec import ShotControl, StudioSpec


def test_script_breakdown_emits_sfx_with_cue_and_offset():
    from agents.script_breakdown_agent import run_script_breakdown_agent

    draft = {
        "scenes": [
            {
                "index": 0,
                "title": "ورود",
                "action": "لیلا می‌خندد و وارد اتاق می‌شود.",
                "duration_sec": 5,
                "story_beat": "entrance",
            },
            {
                "index": 1,
                "title": "قلم",
                "action": "قلم‌مو آبی را از جعبه برمی‌دارد.",
                "duration_sec": 4,
                "story_beat": "reveal",
            },
        ]
    }
    out = run_script_breakdown_agent(draft)
    assert out["version"] == "2"
    s0 = out["shots"][0]
    assert s0.get("sfx")
    cues = {e["cue_id"] for e in s0["sfx"]}
    assert any("laugh" in c or "vocal" in c for c in cues)
    assert any("footstep" in c or "whoosh" in c for c in cues)
    for e in s0["sfx"]:
        assert 0.0 <= float(e["offset_frac"]) <= 1.0
        assert e.get("reason_fa")
    s1 = out["shots"][1]
    assert any("prop" in e["cue_id"] or "hit" in e["cue_id"] for e in s1["sfx"])


def test_literary_screenplay_lists_sfx_cues():
    from agents.literary_screenplay_agent import run_literary_screenplay_agent
    from tools.studio_api import compile_studio_spec

    spec = StudioSpec(
        title="فانوس",
        style_id="symmetrical_pastel_cinema",
        grade="pastel_muted",
        emotion="happy",
        runtime_seconds=10,
        character_path=None,
        shots=[
            ShotControl(
                title="خنده",
                action="لیلا می‌خندد و قدم می‌زند.",
                duration_sec=5,
                pose="walk",
                story_beat="entrance",
                camera="static",
                shot_size="WS",
                composition="C",
                expression="happy",
            )
        ],
    )
    compiled = compile_studio_spec(spec)
    storyboard = {
        "shots": [
            {
                "shot_id": 0,
                "action": spec.shots[0].action,
                "sfx": [
                    {
                        "cue_id": "vocal_laugh",
                        "offset_frac": 0.2,
                        "kind": "vocal",
                        "reason_fa": "خنده",
                    }
                ],
            }
        ]
    }
    out = run_literary_screenplay_agent(
        spec,
        storyboard=storyboard,
        cinematography=compiled.cinematography,
        continuity=compiled.continuity,
    )
    assert "SFX" in out["screenplay_md"] or "افکت صدا" in out["screenplay_md"]
    assert "vocal_laugh" in out["screenplay_md"]
    assert out["shots"][0].get("sfx")


def test_narrative_catalog_cues_exist_and_wavs():
    from agents.audio_cue_agent import load_audio_catalog
    from tools.audio_cues import ensure_audio_cue_files

    ensure_audio_cue_files()
    cat = load_audio_catalog()
    cues = cat["cues"]
    for cid in ("vocal_laugh", "whoosh_move", "prop_pickup", "cloth_rustle"):
        assert cid in cues, cid
        rel = cues[cid]["file"]
        assert (ROOT / "libraries" / "audio" / rel).is_file()


def test_audio_cue_honors_explicit_sfx_and_persian_keywords():
    from agents.audio_cue_agent import run_audio_cue_agent
    from tools.audio_cues import ensure_audio_cue_files

    ensure_audio_cue_files()
    out = run_audio_cue_agent(
        [
            {
                "shot_id": 0,
                "action": "لیلا می‌خندد.",
                "story_beat": "reaction",
                "duration_frames": 48,
                "sfx": [
                    {
                        "cue_id": "vocal_laugh",
                        "offset_frac": 0.25,
                        "kind": "vocal",
                        "reason_fa": "خنده",
                    }
                ],
            }
        ],
        fps=24,
        emotion="happy",
    )
    oneshots = [e for e in out["events"] if e.get("role") != "bed"]
    assert any(e["cue"] == "vocal_laugh" for e in oneshots)
    laugh = next(e for e in oneshots if e["cue"] == "vocal_laugh")
    assert laugh["startFrame"] == 12  # 0.25 * 48
    assert "screenplay" in (laugh.get("reason") or "") or "sfx" in (
        laugh.get("reason") or ""
    )

    # Persian keyword path without explicit sfx
    out2 = run_audio_cue_agent(
        [
            {
                "shot_id": 0,
                "action": "قهرمان وارد می‌شود و قدم می‌زند.",
                "story_beat": "entrance",
                "duration_frames": 36,
            }
        ],
        fps=24,
    )
    cues = [e["cue"] for e in out2["events"] if e.get("role") != "bed"]
    assert any("footstep" in c or "whoosh" in c for c in cues)


def test_remotion_props_include_screenplay_sfx(tmp_path: Path):
    from tools.remotion_emitter import write_story_composition_props
    from tools.studio_api import compile_studio_spec

    spec = StudioSpec(
        title="خنده",
        style_id="symmetrical_pastel_cinema",
        grade="pastel_muted",
        emotion="happy",
        runtime_seconds=6,
        character_path=None,
        shots=[
            ShotControl(
                title="a",
                action="لیلا می‌خندد.",
                duration_sec=4,
                pose="idle",
                story_beat="reaction",
                camera="static",
                shot_size="MS",
                composition="C",
                expression="happy",
            )
        ],
    )
    compiled = compile_studio_spec(spec)
    # inject sfx onto storyboard like breakdown→storyboard would
    sb = dict(compiled.storyboard)
    shots = list(sb.get("shots") or [])
    if shots:
        shots[0] = {
            **shots[0],
            "sfx": [
                {
                    "cue_id": "vocal_laugh",
                    "offset_frac": 0.3,
                    "kind": "vocal",
                    "reason_fa": "خنده",
                }
            ],
        }
        sb["shots"] = shots
    write_story_composition_props(
        tmp_path,
        storyboard=sb,
        cinematography=compiled.cinematography,
        timing=compiled.timing,
        continuity=compiled.continuity,
        style_profile={
            "style_id": spec.style_id,
            "grade": spec.grade,
            "pace": spec.pace,
            "emotion": spec.emotion,
        },
        character_path=None,
    )
    props = json.loads((tmp_path / "story_props.json").read_text(encoding="utf-8"))
    cues = [e.get("cue") for e in (props.get("audioTimeline") or {}).get("events") or []]
    assert "vocal_laugh" in cues
