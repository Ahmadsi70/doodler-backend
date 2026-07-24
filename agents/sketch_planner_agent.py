"""
Agent for planning the DoodlerGAN sketch part sequence based on the user's brief.
"""
from typing import Dict, Any
from doodler_ir import SketchSequence, PartNode, SketchBrief
from llm.deepseek_client import chat_json
import json

def plan_sketch_parts(brief: SketchBrief) -> SketchSequence:
    prompt = f"""
    You are a creative Sketch Planner. The user wants to draw: '{brief.user_prompt}'
    Create a logical sequence of parts to draw this creature using a part-based generation approach.
    Budget: {brief.num_parts_budget} parts maximum.
    
    Allowed part types: ["body", "head", "eye", "mouth", "wing", "leg", "arm", "tail", "horn", "other"]
    
    Output a JSON object with:
    1. "creature_name": A fun name for this creature.
    2. "lore": A short back-story (1-2 sentences).
    3. "parts": A list of objects, each with "part_type" and "prompt".
    """
    
    data = chat_json(role="narrative", system="You are a Sketch Planner.", user=prompt)
    if not data or not data.get("parts"):
        raise ValueError("LLM returned empty or invalid sketch data")
    
    parts = []
    for i, p in enumerate(data.get("parts", [])):
        parts.append(PartNode(
            id=f"part_{i}",
            part_type=p["part_type"],
            order=i,
            prompt=p.get("prompt", "")
        ))
        
    return SketchSequence(
        creature_name=data.get("creature_name", "Unknown"),
        lore=data.get("lore", ""),
        parts=parts
    )
