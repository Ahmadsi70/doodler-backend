"""
Agent for breaking down a story into a chronological sequence of scenes.
"""
from doodler_ir import TimelineSequence, AnimationScene, SketchSequence
from llm.deepseek_client import chat_json
import json

def direct_timeline(sketch: SketchSequence, target_duration: int = 15) -> TimelineSequence:
    prompt = f"""
    You are a Timeline Director for an animation.
    We have a creature named '{sketch.creature_name}'.
    Lore: {sketch.lore}
    
    Break this lore down into a chronological sequence of short scenes.
    The total animation duration MUST be exactly {target_duration} seconds.
    Make sure the sum of all scenes perfectly fills {target_duration} seconds.
    Each scene must have a start_time and end_time (in seconds, e.g., 0.0 to 3.0).
    For each scene, select the MOST appropriate animation type from the following options ONLY:
    ["walk", "run", "jump", "dance", "wave", "idle"]
    
    Also, write a short, descriptive sound effect prompt (Foley) for each scene (e.g. 'comical boing sound followed by a heavy thud'). Do NOT write dialogue.
    
    Output a JSON object with a single key "scenes" containing a list of objects. Each object must have:
    - "start_time" (float)
    - "end_time" (float)
    - "motion_type" (string)
    - "sfx_prompt" (string)
    """
    
    data = chat_json(role="narrative", system="You are a Timeline Director. Pantomime style.", user=prompt) or {}
    scenes_data = data.get("scenes", [])
    
    scenes = []
    # Fallback if empty or failed
    if not scenes_data:
        scenes.append(AnimationScene(start_time=0.0, end_time=5.0, motion_type="idle", sfx_prompt="wind blowing"))
    else:
        for s in scenes_data:
            try:
                st = float(s.get("start_time", 0.0))
                et = float(s.get("end_time", 5.0))
            except (ValueError, TypeError):
                st, et = 0.0, 5.0
            
            scenes.append(AnimationScene(
                start_time=st,
                end_time=et,
                motion_type=s.get("motion_type", "idle"),
                sfx_prompt=s.get("sfx_prompt", "")
            ))
            
    # Mathematically ensure the total duration matches target_duration exactly
    if scenes:
        total_dur = max(s.end_time for s in scenes)
        if total_dur > 0 and abs(total_dur - target_duration) > 0.01:
            scale = target_duration / total_dur
            for s in scenes:
                s.start_time *= scale
                s.end_time *= scale
            
    return TimelineSequence(scenes=scenes)
