"""Test real animation pipeline — creates a short video using actual models.

Reco Mode:
  1. Try RunPod (cloud GPU) — if endpoint is available
  2. Fall back to local CPU — if no GPU available (very slow, warning shown)

Usage:
    python fixtures/test_real_animation.py                     # auto-detect
    python fixtures/test_real_animation.py --force-runpod       # force RunPod
    python fixtures/test_real_animation.py --force-local        # force local CPU
    python fixtures/test_real_animation.py --output out/my_video.mp4
"""

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["MOCK_MODE"] = "0"

SCENE_BOARD = {
    "title": "Real Animation Test",
    "brief": "A short walk cycle test with real AnimateDiff models",
    "total_duration_sec": 4.0,
    "fps": 8,
    "shots": [
        {
            "shot_id": 0,
            "title": "Walk",
            "action": "A cute cartoon cat walks forward in a sunny meadow",
            "duration_sec": 4.0,
            "story_beat": "approach",
            "motion": {"character_motion": "walk", "camera_motion": "pan_left"},
            "expression": {"primary": "happy"},
            "scene": {"environment_fa": "meadow", "lighting_fa": "day"},
            "positive_prompt": (
                "a cute cartoon cat walking in a sunny meadow, "
                "vibrant colors, 2D animation style, Pixar style, "
                "soft lighting, highly detailed, cute face"
            ),
            "negative_prompt": (
                "blurry, low quality, distorted, extra limbs, "
                "bad anatomy, watermark, text, signature"
            ),
        }
    ],
}

MODEL_CONFIG = {
    "base_model": "sd-v1-5",
    "motion_module": "mm_sd_v15",
    "inference_mode": "standard",
    "num_inference_steps": 25,
    "guidance_scale": 7.5,
    "context_batch_size": 4,
    "fps": 8,
    "seed": 42,
}


def check_local_gpu() -> str | None:
    """Check if local GPU is available and has enough VRAM."""
    try:
        import torch
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            vram_gb = props.total_mem / 1e9
            name = props.name
            if vram_gb >= 8:
                return f"{name} ({vram_gb:.1f} GB)"
            return None
        return None
    except ImportError:
        return None


def check_runpod() -> bool:
    """Check if RunPod endpoint is available."""
    try:
        from libraries.runpod_client import RunPodClient
        client = RunPodClient()
        ok = client.health_check()
        if ok:
            print(f"  RunPod endpoint: {client.endpoint_id} OK")
        return ok
    except Exception as e:
        print(f"  RunPod check failed: {e}")
        return False


def save_scene_json(output_dir: Path) -> Path:
    """Save the test scene to a JSON file and return the path."""
    path = output_dir / "scene_board.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"scene_board": SCENE_BOARD, "model_config": MODEL_CONFIG}, f, indent=2)
    return path


def run_local(output_dir: Path) -> dict:
    """Run the full pipeline locally (may be slow on CPU)."""
    from runpod_handler import run_pipeline

    print(f"\n  Running locally...")
    print(f"  WARNING: AnimateDiff on CPU is extremely slow.")
    print(f"  Expect 10-60 minutes for even 32 frames.\n")

    result = run_pipeline(
        SCENE_BOARD,
        MODEL_CONFIG,
        output_dir=output_dir,
        on_step=lambda msg: print(f"    [{time.strftime('%H:%M:%S')}] {msg}"),
    )
    return result


def run_on_runpod(output_dir: Path) -> dict:
    """Submit the job to RunPod and wait for completion."""
    from libraries.runpod_client import RunPodClient

    client = RunPodClient()

    print(f"  Submitting to RunPod endpoint: {client.endpoint_id}")

    def on_status(msg: str) -> None:
        print(f"    [{time.strftime('%H:%M:%S')}] {msg}")

    result = client.run_animation_pipeline(
        SCENE_BOARD,
        MODEL_CONFIG,
        timeout=1200,
        on_status=on_status,
    )

    video_b64 = result.get("video_base64", "")
    if video_b64:
        import base64
        video_path = output_dir / "output.mp4"
        with open(video_path, "wb") as f:
            f.write(base64.b64decode(video_b64))
        render_video_path = str(video_path)
    else:
        render_video_path = result.get("video_path", "")

    result.pop("video_base64", None)
    return result


def verify_video(result: dict, output_dir: Path) -> list[str]:
    """Verify the output video and return list of issues (empty = perfect)."""
    issues = []
    video_path = result.get("video_path", "")

    if not video_path or not os.path.isfile(video_path):
        # Check output_dir for mp4
        candidates = list(output_dir.rglob("*.mp4"))
        if candidates:
            video_path = str(candidates[0])
            result["video_path"] = video_path
        else:
            issues.append("No video file found in output")
            return issues

    file_size = os.path.getsize(video_path)
    result["file_size_bytes"] = file_size

    checks = {
        "ok": result.get("ok", False),
        "file exists": os.path.isfile(video_path),
        "file > 10 KB": file_size > 10240,
        "total_frames > 0": result.get("total_frames", 0) > 0,
        "duration_sec > 0": result.get("duration_sec", 0) > 0,
    }

    for check, passed in checks.items():
        if not passed:
            issues.append(f"FAIL: {check}")

    if not issues:
        print(f"\n  All checks passed!")
        print(f"  Video: {video_path}")
        print(f"  Size:  {file_size / 1024:.1f} KB ({file_size} bytes)")
        print(f"  Duration: {result.get('duration_sec', 0):.1f}s")
        print(f"  Frames: {result.get('total_frames', 0)} @ {result.get('fps', 0)}fps")

    return issues


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test real animation pipeline (RunPod or local)"
    )
    parser.add_argument("--output", "-o", type=str, default="out/test_real",
                        help="Output directory")
    parser.add_argument("--force-runpod", action="store_true",
                        help="Force use RunPod (fail if unavailable)")
    parser.add_argument("--force-local", action="store_true",
                        help="Force local execution")
    parser.add_argument("--save-input", action="store_true",
                        help="Save scene_board.json and exit (for manual upload)")
    args = parser.parse_args()

    output_dir = Path(args.output)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save input for inspection
    scene_json = save_scene_json(output_dir)
    print(f"\n  Scene board saved: {scene_json}")

    if args.save_input:
        print("  --save-input: exiting (scene saved for manual upload)")
        return

    # Decide execution mode
    local_gpu = check_local_gpu()

    if args.force_local:
        mode = "local"
    elif args.force_runpod:
        if check_runpod():
            mode = "runpod"
        else:
            print("  ERROR: --force-runpod but RunPod endpoint unavailable")
            sys.exit(1)
    elif local_gpu:
        mode = "local_gpu"
        print(f"  Local GPU detected: {local_gpu}")
    elif check_runpod():
        mode = "runpod"
    else:
        mode = "local"
        print("  No GPU detected locally or on RunPod.")
        print("  Falling back to CPU (will be very slow).")

    print(f"  Mode: {mode}\n")

    # Run
    start = time.time()

    if mode == "runpod":
        result = run_on_runpod(output_dir)
    else:
        result = run_local(output_dir)

    elapsed = time.time() - start

    # Save result report
    report_path = output_dir / "result.json"
    with open(report_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    # Verify
    print(f"\n{'='*50}")
    issues = verify_video(result, output_dir)

    if issues:
        print(f"\n  VERIFICATION ISSUES ({len(issues)}):")
        for i in issues:
            print(f"    - {i}")
    else:
        print(f"\n  VIDEO VERIFICATION: PASSED")
        print(f"  Result report: {report_path}")

    print(f"\n  Time: {elapsed:.1f}s")
    print(f"  Output: {output_dir}")

    if issues:
        sys.exit(1)
    print("  TEST: PASSED")


if __name__ == "__main__":
    main()
