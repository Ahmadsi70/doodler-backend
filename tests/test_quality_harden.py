"""C — quality harden: LLM probe, Pro props characterRig, remotion_ready."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from tools.remotion_emitter import remotion_ready, write_story_composition_props
from tools.studio_profiles import find_ffmpeg
from tools.williams_character_bridge import enrich_character_rig


def test_llm_disabled_without_forced_flag(monkeypatch):
    from agents.llm_enrich import llm_enabled

    monkeypatch.delenv("STORY_USE_LLM", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert llm_enabled({"use_llm": False}) is False


def test_pro_props_carry_character_rig(tmp_path: Path):
    rig = enrich_character_rig(job_dir=tmp_path)
    path = write_story_composition_props(
        tmp_path,
        storyboard={
            "shots": [
                {
                    "shot_id": 0,
                    "title": "Enter",
                    "action": "Walk in",
                    "duration_sec": 2.5,
                }
            ]
        },
        character_rig=rig,
        style_profile={
            "style_id": "symmetrical_pastel_cinema",
            "engine": {"grade": "pastel_muted", "pace": "measured"},
        },
    )
    props = json.loads(path.read_text(encoding="utf-8"))
    assert props.get("characterRig")
    assert props["characterRig"].get("keyframes")
    assert props.get("grade") == "pastel_muted"


@pytest.mark.skipif(not remotion_ready(), reason="remotion not installed")
def test_remotion_ready_true():
    assert remotion_ready() is True


@pytest.mark.skipif(not find_ffmpeg(), reason="ffmpeg required")
def test_smoke_render_script_exists():
    assert (ROOT / "scripts" / "smoke_render.py").is_file()
    assert (ROOT / "scripts" / "smoke_remotion.py").is_file()
