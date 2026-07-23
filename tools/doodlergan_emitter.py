"""
Generates the inference script for DoodlerGAN based on the SketchSequence.
"""
import os
from pathlib import Path
from doodler_ir import SketchSequence

def emit_doodlergan_script(sketch: SketchSequence, out_dir: Path) -> Path:
    script_path = out_dir / "run_doodlergan.py"
    
    parts_list_str = "[" + ", ".join([f"'{p.part_type}'" for p in sketch.parts]) + "]"
    
    code = f"""
# Auto-generated DoodlerGAN Inference Script
import os
import torch
# Assumes facebookresearch/DoodlerGAN is cloned and available in PYTHONPATH
# from models.part_selector import PartSelector
# from models.part_generator import PartGenerator
# from utils.rendering import save_stroke

def generate_sketch():
    print("Starting DoodlerGAN for '{sketch.creature_name}'...")
    sequence = {parts_list_str}
    
    out_dir = "frames"
    os.makedirs(out_dir, exist_ok=True)
    
    # Pseudo-code for inference:
    # selector = PartSelector.load_pretrained('creative_birds')
    # generator = PartGenerator.load_pretrained('creative_birds')
    
    # canvas = torch.zeros((1, 3, 256, 256))
    
    for i, part in enumerate(sequence):
        print(f"Drawing part {{i+1}}: {{part}}")
        # next_part = selector(canvas) # if we let the model decide, or override with sequence
        # canvas = generator(canvas, part)
        # save_stroke(canvas, os.path.join(out_dir, f"frame_{{i:03d}}.png"))
        
        # Mocking the save for now:
        with open(os.path.join(out_dir, f"frame_{{i:03d}}.txt"), "w") as f:
            f.write(f"Drew {{part}}")
            
    print(f"Sketch generation complete! Saved {{len(sequence)}} frames.")

if __name__ == "__main__":
    generate_sketch()
"""
    os.makedirs(out_dir, exist_ok=True)
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(code.strip())
        
    return script_path
