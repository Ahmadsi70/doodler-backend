"""
The main workflow pipeline for DoodlerGAN + Animated Drawings.
Connects the Sketch Planner, Motion Director, and emitters.
"""
from pathlib import Path
from doodler_ir import SketchBrief, DoodlerStudioSpec
from agents.sketch_planner_agent import plan_sketch_parts
from agents.timeline_director_agent import direct_timeline
from tools.doodlergan_emitter import emit_doodlergan_script
from tools.animated_drawings_emitter import emit_animated_drawings_script
import json

def run_doodle_pipeline(user_prompt: str, target_duration: int, out_dir: str):
    print(f"\n--- Starting Doodler Pipeline ---")
    print(f"Brief: {user_prompt}")
    
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    # 1. Brief Creation
    brief = SketchBrief(user_prompt=user_prompt)
    
    # 2. Sketch Planning
    print("\n[1/4] Planning sketch sequence...")
    sketch = plan_sketch_parts(brief)
    print(f"Creature: {sketch.creature_name}")
    print(f"Parts sequence: {[p.part_type for p in sketch.parts]}")
    
    # 3. Timeline Direction
    print(f"\n[2/4] Directing timeline sequences (Target: {target_duration}s)...")
    timeline = direct_timeline(sketch, target_duration)
    print(f"Number of scenes: {len(timeline.scenes)}")
    
    # Combine into Spec
    spec = DoodlerStudioSpec(brief=brief, sketch=sketch, timeline=timeline)
    
    with open(out_path / "doodler_spec.json", "w", encoding="utf-8") as f:
        f.write(spec.model_dump_json(indent=2))
        
    # 4. Emit inference scripts
    print("\n[3/4] Generating DoodlerGAN python script...")
    doodler_script = emit_doodlergan_script(sketch, out_path / "doodler_src")
    print(f"Saved: {doodler_script}")
    
    print("\n[4/4] Generating Animated Drawings python script...")
    anim_script = emit_animated_drawings_script(timeline, out_path / "anim_src", image_path="sketch.png")
    print(f"Saved: {anim_script}")
    
    print("\n--- Pipeline Complete ---")
    print("Next steps:")
    print(f"1. Run `python {doodler_script}`")
    print(f"2. Run `python {anim_script}`")
    
    return spec

if __name__ == "__main__":
    run_doodle_pipeline("A funny bird with big eyes and a tiny tail", 15, "out/doodle_test")
