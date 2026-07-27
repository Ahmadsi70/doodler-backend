"""RunPod Serverless Handler — runs the full animation pipeline on cloud GPU.

Deploy this on RunPod as a serverless endpoint. The handler:
  1. Receives SceneBoard + ModelConfig as JSON
  2. Sets up models (downloads if missing)
  3. Runs Layers 1–8 (prompt → frames → motion → SFX → sync → compose)
  4. Returns the output video + metadata as base64

Usage (local test):
    python runpod_handler.py --input test_scene.json --output out/result.mp4
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any

os.environ["MOCK_MODE"] = "0"


def load_scene_board(data: dict[str, Any]):
    """Reconstruct a SceneBoard from a dict."""
    from libraries.scene_board import SceneBoard
    return SceneBoard(**data)


def run_pipeline(
    scene_board_data: dict[str, Any],
    model_config_data: dict[str, Any] | None = None,
    output_dir: str | Path | None = None,
    on_step: callable | None = None,
) -> dict[str, Any]:
    """Run Layers 1–8 and return output metadata."""
    from libraries.model_config import ModelConfig
    from libraries.model_loader import check_models, get_pipeline

    from animatediff.inference.infer_anim import generate_from_board
    from animatediff.motion.motion_analyzer import analyze_frames
    from animatediff.sfx.sfx_selector import select_sfx
    from animatediff.sync.sfx_sync import sync_sfx
    from animatediff.compose.video_composer import compose_video

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="runpod_anim_"))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    steps: list[str] = []

    def step(msg: str) -> None:
        steps.append(msg)
        if on_step:
            on_step(msg)

    # Build config
    mc = ModelConfig(**(model_config_data or {}))
    board = load_scene_board(scene_board_data)

    # Check models
    model_status = check_models(mc)
    if not model_status["all_available"]:
        missing = ", ".join(m["key"] for m in model_status["missing"])
        step(f"Downloading missing models: {missing}")
        _download_models(model_status["missing"])

    # Layer 4: Generate frames
    step(f"Generating {board.shot_count} shot(s)...")
    gen_result = generate_from_board(
        board, mc, output_root=output_dir / "frames",
    )
    manifest_path = gen_result["manifest_path"]
    step(f"Generated {gen_result['total_frames']} frames")

    # Layer 5: Motion detection
    step("Analyzing motion...")
    motion_report = analyze_frames(
        manifest_path,
        output_dir=str(output_dir / "motion"),
        fps=mc.fps,
    )
    motion_report_path = str(output_dir / "motion" / "motion_report.json")
    step(f"Motion: {motion_report.total_frames} frames, {len(motion_report.global_events)} events")

    # Layer 6: SFX selection
    step("Selecting SFX...")
    sfx_timeline = select_sfx(
        motion_report_path,
        output_dir=str(output_dir / "sfx"),
        fps=mc.fps,
    )
    sfx_timeline_path = str(output_dir / "sfx" / "sfx_timeline.json")
    step(f"SFX: {len(sfx_timeline.events)} events")

    # Layer 7: SFX sync
    step("Syncing audio...")
    sync_report = sync_sfx(
        sfx_timeline_path,
        output_dir=str(output_dir / "audio"),
        fps=mc.fps,
    )
    audio_path = str(output_dir / "audio" / "soundtrack.wav")
    step(f"Audio: {os.path.getsize(audio_path)} bytes")

    # Layer 8: Compose video
    step("Composing video...")
    compose_report = compose_video(
        manifest_path,
        audio_path=audio_path,
        fps=mc.fps,
        output_dir=output_dir / "video",
        on_step=step,
    )
    video_path = compose_report.video_path
    step(f"Video: {video_path} ({compose_report.file_size_bytes} bytes)")

    return {
        "ok": compose_report.ok,
        "video_path": str(video_path),
        "audio_path": audio_path,
        "motion_report_path": motion_report_path,
        "sfx_timeline_path": sfx_timeline_path,
        "total_frames": compose_report.total_frames,
        "duration_sec": compose_report.duration_sec,
        "fps": compose_report.fps,
        "file_size_bytes": compose_report.file_size_bytes,
        "output_dir": str(output_dir),
        "steps": steps,
    }


def _download_models(missing: list[dict[str, Any]]) -> None:
    """Download missing model files."""
    import requests
    from libraries.model_loader import resolve_model_path
    for m in missing:
        key = m["key"]
        url = m.get("download_url", "")
        dest = resolve_model_path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            continue
        print(f"Downloading {key} -> {dest} ...")
        if "huggingface.co" in url:
            _hf_download(key, dest)
        else:
            r = requests.get(url, stream=True, timeout=300)
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)


def _hf_download(key: str, dest: Path) -> None:
    """Download from HuggingFace with resume support."""
    import requests
    HF_MAP = {
        "sd-v1-5": (
            "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.ckpt",
        ),
        "mm_sd_v15": (
            "https://huggingface.co/guoyww/animatediff/resolve/main/mm_sd_v15.ckpt",
        ),
    }
    url = HF_MAP.get(key, [""])[0]
    if not url:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    resume_bytes = dest.stat().st_size if dest.exists() else 0
    headers = {"Range": f"bytes={resume_bytes}-"} if resume_bytes else {}
    r = requests.get(url, stream=True, timeout=600, headers=headers)
    mode = "ab" if resume_bytes else "wb"
    with open(dest, mode) as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)


# ── RunPod serverless handler ────────────────────────────────────────────


def runpod_handler(job: dict[str, Any]) -> dict[str, Any]:
    """RunPod serverless entry point.

    Called by RunPod's infrastructure for each job.
    """
    job_input = job.get("input", {})
    scene_board = job_input.get("scene_board", {})
    model_config = job_input.get("model_config", {})

    if not scene_board:
        return {"error": "Missing 'scene_board' in input", "status": "failed"}

    try:
        result = run_pipeline(scene_board, model_config)

        encode_output = job_input.get("encode_video", True)
        if encode_output and os.path.isfile(result.get("video_path", "")):
            with open(result["video_path"], "rb") as f:
                result["video_base64"] = base64.b64encode(f.read()).decode("utf-8")

        result["status"] = "completed"
        return result

    except Exception as e:
        traceback.print_exc()
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "status": "failed",
        }


# ── CLI entry point (local testing) ──────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Run animation pipeline (local or RunPod)")
    parser.add_argument("--input", "-i", type=str, default="",
                        help="Path to JSON file with scene_board + model_config")
    parser.add_argument("--output", "-o", type=str, default="out/runpod_result",
                        help="Output directory")
    parser.add_argument("--no-clean", action="store_true",
                        help="Keep output directory after completion")
    parser.add_argument("--on-runpod", action="store_true",
                        help="Use RunPod serverless endpoint instead of local execution")
    args = parser.parse_args()

    if args.on_runpod:
        _run_on_runpod(args)
        return

    # Load input
    if args.input:
        with open(args.input) as f:
            payload = json.load(f)
    else:
        payload = {
            "scene_board": {
                "title": "RunPod Test",
                "brief": "Test animation",
                "total_duration_sec": 4.0,
                "fps": 8,
                "shots": [
                    {
                        "shot_id": 0, "title": "Walk",
                        "action": "A cartoon character walks forward in a park",
                        "duration_sec": 4.0, "story_beat": "approach",
                        "motion": {"character_motion": "walk", "camera_motion": "pan_left"},
                        "expression": {"primary": "neutral"},
                        "scene": {"environment_fa": "park", "lighting_fa": "day"},
                        "positive_prompt": "a happy cartoon character walking in a sunny park, vibrant colors, 2D animation style",
                        "negative_prompt": "blurry, low quality, distorted",
                    }
                ],
            }
        }

    output_dir = Path(args.output)
    if output_dir.exists() and not args.no_clean:
        shutil.rmtree(output_dir)

    def on_step(msg: str) -> None:
        print(f"  [{time.strftime('%H:%M:%S')}] {msg}")

    print(f"Starting animation pipeline...")
    result = run_pipeline(
        payload["scene_board"],
        payload.get("model_config"),
        output_dir=output_dir,
        on_step=on_step,
    )

    print(f"\n{'='*50}")
    print(f"Pipeline complete!")
    print(f"  Video: {result['video_path']}")
    print(f"  Size:  {result['file_size_bytes']} bytes")
    print(f"  Frames: {result['total_frames']} @ {result['fps']}fps")
    print(f"  Duration: {result['duration_sec']}s")
    print(f"  Steps: {len(result['steps'])}")
    for s in result['steps']:
        print(f"    - {s}")


def _run_on_runpod(args: argparse.Namespace) -> None:
    """Submit job to RunPod serverless endpoint and wait for result."""
    from libraries.runpod_client import RunPodClient

    client = RunPodClient()
    if not client.health_check():
        print("RunPod endpoint is not available. Check RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID.")
        sys.exit(1)

    if args.input:
        with open(args.input) as f:
            payload = json.load(f)
    else:
        print("Error: --input required when using --on-runpod")
        sys.exit(1)

    def on_status(msg: str) -> None:
        print(f"  [{time.strftime('%H:%M:%S')}] {msg}")

    print(f"Submitting job to RunPod endpoint {client.endpoint_id}...")
    result = client.run_animation_pipeline(
        payload.get("scene_board", {}),
        payload.get("model_config"),
        timeout=1200,
        on_status=on_status,
    )

    video_b64 = result.get("video_base64", "")
    if video_b64:
        output_path = Path(args.output) / "output.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(video_b64))
        print(f"Video saved: {output_path}")

    result.pop("video_base64", None)
    report_path = Path(args.output) / "report.json"
    with open(report_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Report saved: {report_path}")
    print(json.dumps({k: v for k, v in result.items() if k != "steps"}, indent=2))


if __name__ == "__main__":
    main()
