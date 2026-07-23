"""Golden Pro — Remotion props contract (stable without full video encode)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GOLDEN = ROOT / "fixtures" / "golden" / "story_pro_props"
BRIEF = (
    "A lonely character enters a quiet room.\n\n"
    "Then they react in shock because the letter burns.\n\n"
    "They leave quietly."
)


def _build_props(tmp_path: Path) -> dict:
    from agents.story_chain import run_story_agent_chain
    from tools.remotion_emitter import write_story_composition_props

    chain = run_story_agent_chain(
        BRIEF, tmp_path, extras={"runtime_seconds": 24, "use_llm": False}
    )
    path = write_story_composition_props(
        tmp_path,
        storyboard=chain.storyboard,
        cinematography=chain.cinematography,
        timing=chain.animation_timing,
        continuity=chain.continuity,
        style_profile={
            "style_id": "symmetrical_pastel_cinema",
            "engine": {
                "grade": "pastel_muted",
                "pace": "measured",
                "camera": "locked_symmetric",
            },
        },
        title="StoryProGolden",
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_pro_props_golden_contract(tmp_path: Path):
    props = _build_props(tmp_path)
    expected_path = GOLDEN / "expected" / "props_contract.json"
    assert expected_path.is_file(), "missing golden fixture"
    contract = json.loads(expected_path.read_text(encoding="utf-8"))

    assert props["fps"] == contract["fps"]
    assert props["grade"] == contract["grade"]
    assert len(props["shots"]) >= contract["min_shots"]
    keys = set(contract["required_shot_keys"])
    for shot in props["shots"]:
        missing = keys - set(shot.keys())
        assert not missing, missing
    # Reaction beat should carry craft-driven push when present
    cameras = {s.get("camera") for s in props["shots"]}
    assert "motivated_push" in cameras or "static" in cameras
    assert props["continuity"]["lineSide"] in {"left", "right"}


def test_pro_props_include_craft_hints(tmp_path: Path):
    props = _build_props(tmp_path)
    hinted = [s for s in props["shots"] if s.get("craftHints")]
    assert hinted, "expected craftHints on at least one shot"
    hint = hinted[0]["craftHints"]
    assert "do" in hint and "dont" in hint
