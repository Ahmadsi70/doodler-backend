"""
Agent for selecting the appropriate motion for Animated Drawings based on the creature's lore.
"""
from doodler_ir import MotionScenario, SketchSequence
from llm.deepseek_client import chat_json
import json

def direct_motion(sketch: SketchSequence) -> MotionScenario:
    prompt = f"""
    You are a Motion Director.
    We have a creature named '{sketch.creature_name}'.
    Lore: {sketch.lore}
    
    Select the most appropriate animation type from the following options:
    ["walk", "run", "jump", "dance", "wave", "idle"]
    
    Also, write a short, descriptive sound effect prompt (Foley) that matches this movement (e.g. 'comical boing sound followed by a heavy thud'). Do NOT write dialogue.
    
    Output a JSON object with:
    1. "motion_type"
    2. "sfx_prompt"
    """
    
    data = chat_json(role="narrative", system="You are a Foley Sound Designer and Motion Director. Pantomime style.", user=prompt) or {}
    
    return MotionScenario(
        motion_type=data.get("motion_type", "idle"),
        sfx_prompt=data.get("sfx_prompt", "")
    )
