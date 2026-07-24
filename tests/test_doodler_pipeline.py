import pytest
import os
import shutil
from pathlib import Path
from unittest.mock import patch
from doodler_pipeline import run_doodle_pipeline
from doodler_ir import SketchSequence, TimelineSequence, SketchBrief

@pytest.fixture
def temp_out_dir(tmp_path):
    out_dir = tmp_path / "test_out"
    yield str(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)

def mock_chat_json_happy_path(**kwargs):
    system = kwargs.get("system", "")
    if "Sketch Planner" in system:
        return {
            "creature_name": "TestaDoodle",
            "lore": "A testing doodle",
            "parts": [
                {"part_type": "body", "prompt": "a fluffy blue body"},
                {"part_type": "head", "prompt": "a small head"}
            ]
        }
    elif "Timeline Director" in system:
        # 2 scenes, summing exactly to 15 seconds
        return {
            "scenes": [
                {"start_time": 0.0, "end_time": 7.5, "motion_type": "walk", "sfx_prompt": "walking sound"},
                {"start_time": 7.5, "end_time": 15.0, "motion_type": "jump", "sfx_prompt": "jump sound"}
            ]
        }
    return {}

def mock_chat_json_empty_path(**kwargs):
    # Simulates an LLM failure or empty response
    return None

def mock_chat_json_math_error(**kwargs):
    system = kwargs.get("system", "")
    if "Sketch Planner" in system:
        return mock_chat_json_happy_path(**kwargs)
    elif "Timeline Director" in system:
        # LLM math error: target is 15s, but LLM only provides 10s total!
        return {
            "scenes": [
                {"start_time": 0.0, "end_time": 5.0, "motion_type": "walk", "sfx_prompt": "walking sound"},
                {"start_time": 5.0, "end_time": 10.0, "motion_type": "idle", "sfx_prompt": "idle sound"}
            ]
        }
    return {}

@patch("agents.sketch_planner_agent.chat_json", side_effect=mock_chat_json_happy_path)
@patch("agents.timeline_director_agent.chat_json", side_effect=mock_chat_json_happy_path)
def test_pipeline_happy_path(mock_timeline, mock_sketch, temp_out_dir):
    """Test the pipeline completes successfully when LLM provides valid data."""
    spec = run_doodle_pipeline("A test prompt", 15, temp_out_dir)
    
    assert spec is not None
    assert spec.sketch.creature_name == "TestaDoodle"
    assert len(spec.sketch.parts) == 2
    assert len(spec.timeline.scenes) == 2
    
    # Check if scripts were emitted
    assert (Path(temp_out_dir) / "doodler_spec.json").exists()
    assert (Path(temp_out_dir) / "doodler_src" / "run_doodlergan.py").exists()
    assert (Path(temp_out_dir) / "anim_src" / "run_animated_drawings.py").exists()

@patch("agents.sketch_planner_agent.chat_json", side_effect=mock_chat_json_empty_path)
@patch("agents.timeline_director_agent.chat_json", side_effect=mock_chat_json_empty_path)
def test_pipeline_empty_response(mock_timeline, mock_sketch, temp_out_dir):
    """Test that the pipeline explicitly rejects empty LLM responses instead of silent failure."""
    with pytest.raises(ValueError, match="LLM returned empty or invalid sketch data"):
        run_doodle_pipeline("A test prompt", 15, temp_out_dir)

@patch("agents.sketch_planner_agent.chat_json", side_effect=mock_chat_json_math_error)
@patch("agents.timeline_director_agent.chat_json", side_effect=mock_chat_json_math_error)
def test_pipeline_duration_math_error(mock_timeline, mock_sketch, temp_out_dir):
    """Test that the Timeline Director auto-corrects or raises an error when duration doesn't match target."""
    spec = run_doodle_pipeline("A test prompt", 15, temp_out_dir)
    
    total_duration = max(s.end_time for s in spec.timeline.scenes)
    assert total_duration == 15.0, f"Expected exactly 15.0 seconds, got {total_duration}"
