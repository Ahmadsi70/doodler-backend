"""
Animation export bundle — screenplay, natural-language guides, prompts, engine code.

Why: Story is a construction studio, not an in-tool renderer. Users run exported
artifacts on their chosen engine and hardware.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Literal

try:
    from studio_spec import ShotControl, StudioSpec
except ImportError:
    from ..studio_spec import ShotControl, StudioSpec  # type: ignore

ExportTarget = Literal["prompts", "remotion", "slideshow"]
DEFAULT_TARGETS: tuple[ExportTarget, ...] = ("prompts", "remotion", "slideshow")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    _write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def _run_export_agents(spec: StudioSpec, compiled: Any) -> dict[str, Any]:
    """Run screenplay, director notes, and prompt agents on compiled chain."""
    from agents.animation_prompt_agent import run_animation_prompt_agent
    from agents.director_notes_agent import run_director_notes_agent
    from agents.image_needs_agent import run_image_needs_agent
    from agents.prompt_craft_agent import run_prompt_craft_agent
    from agents.screenplay_agent import run_screenplay_agent

    screenplay = run_screenplay_agent(
        spec,
        storyboard=compiled.storyboard,
        cinematography=compiled.cinematography,
        continuity=compiled.continuity,
    )
    notes = run_director_notes_agent(spec, continuity=compiled.continuity)
    image_needs = run_image_needs_agent(
        spec,
        screenplay=screenplay,
        storyboard=compiled.storyboard,
    )
    prompts = run_prompt_craft_agent(
        spec,
        cinematography=compiled.cinematography,
        continuity=compiled.continuity,
        screenplay=screenplay,
        storyboard=compiled.storyboard,
        image_needs=image_needs,
    )
    motion = run_animation_prompt_agent(
        spec,
        storyboard=compiled.storyboard,
        cinematography=compiled.cinematography,
        timing=compiled.timing,
        continuity=compiled.continuity,
    )
    return {
        "screenplay": screenplay,
        "notes": notes,
        "image_needs": image_needs,
        "prompts": prompts,
        "motion": motion,
    }


def build_screenplay_md(spec: StudioSpec, *, compiled: Any | None = None) -> str:
    """Human-readable screenplay (delegates to ScreenplayAgent)."""
    from tools.studio_api import compile_studio_spec

    compiled = compiled or compile_studio_spec(spec)
    return _run_export_agents(spec, compiled)["screenplay"]["screenplay_md"]


def build_explanation_md(spec: StudioSpec, *, compiled: Any | None = None) -> str:
    """Director notes markdown (delegates to DirectorNotesAgent)."""
    from tools.studio_api import compile_studio_spec

    compiled = compiled or compile_studio_spec(spec)
    return _run_export_agents(spec, compiled)["notes"]["explanation_md"]


def build_shot_prompt(sh: ShotControl, index: int, spec: StudioSpec) -> str:
    """Backward-compat single-shot prompt (prefer PromptCraftAgent batch)."""
    from agents.prompt_craft_agent import run_prompt_craft_agent
    from tools.studio_api import compile_studio_spec

    compiled = compile_studio_spec(spec)
    batch = run_prompt_craft_agent(
        spec,
        cinematography=compiled.cinematography,
        continuity=compiled.continuity,
    )
    for row in batch["shots"]:
        if row["id"] == f"shot_{index:02d}":
            return row["prompt"]
    return batch["shots"][index]["prompt"]


def build_film_prompt(spec: StudioSpec, *, compiled: Any | None = None) -> str:
    """Whole-film prompt (delegates to PromptCraftAgent)."""
    from tools.studio_api import compile_studio_spec

    compiled = compiled or compile_studio_spec(spec)
    return _run_export_agents(spec, compiled)["prompts"]["film_prompt"]


def build_export_preview(spec: StudioSpec) -> dict[str, Any]:
    """Dry-run export agent outputs for UI preview (no disk write)."""
    from tools.studio_api import compile_studio_spec

    compiled = compile_studio_spec(spec)
    agents_out = _run_export_agents(spec, compiled)
    prompt_shots = agents_out["prompts"]["shots"]
    motion_shots = agents_out["motion"]["shots"]
    motion_by_tool: dict[str, dict[str, str]] = {}
    for row in motion_shots:
        sid = str(row.get("id") or "")
        for tool_id, text in (row.get("by_tool") or {}).items():
            motion_by_tool.setdefault(str(tool_id), {})[sid] = str(text)
    return {
        "screenplay_md": agents_out["screenplay"]["screenplay_md"],
        "screenplay_json": agents_out["screenplay"],
        "explanation_md": agents_out["notes"]["explanation_md"],
        "film_prompt": agents_out["prompts"]["film_prompt"],
        "film_motion_prompt": agents_out["motion"]["film_motion_prompt"],
        "prompt_guide_md": agents_out["prompts"]["guide_md"],
        "motion_guide_md": agents_out["motion"]["guide_md"],
        "shot_prompts": {row["id"]: row["prompt"] for row in prompt_shots},
        "shot_negatives": {row["id"]: row["negative"] for row in prompt_shots},
        "shot_motions": {row["id"]: row["motion_prompt"] for row in motion_shots},
        "shot_motions_by_tool": motion_by_tool,
    }


def _export_prompts_from_agent(
    prompt_pack: dict[str, Any],
    root: Path,
    *,
    motion_pack: dict[str, Any] | None = None,
) -> None:
    """Write still + motion prompt files and image_manifest for assembly."""
    prompts = root / "prompts"
    _write_text(prompts / "film.txt", prompt_pack["film_prompt"])
    _write_text(prompts / "guide.md", prompt_pack["guide_md"])
    for row in prompt_pack["shots"]:
        sid = row["id"]
        _write_text(prompts / f"{sid}.txt", row["prompt"])
        _write_text(prompts / f"{sid}_negative.txt", row["negative"])
    # P2: typed assets + assembly manifest (timeline_slot / framing)
    assets = list(prompt_pack.get("assets") or [])
    needs = prompt_pack.get("image_needs") or {}
    if assets or needs:
        manifest = {
            "version": prompt_pack.get("version") or "2",
            "agent": "PromptCraftAgent",
            "assets": assets,
            "image_needs": needs,
            "assembly_notes_fa": needs.get("assembly_notes_fa")
            or "character_ref را ثابت نگه دارید؛ timeline_slot مسیر تایم‌لاین است.",
        }
        _write_json(prompts / "image_manifest.json", manifest)
        assets_dir = prompts / "assets"
        for row in assets:
            aid = str(row.get("asset_id") or "asset").replace("/", "_")
            body = str(row.get("prompt") or "")
            neg = str(row.get("negative") or "")
            _write_text(assets_dir / f"{aid}.txt", body)
            if neg:
                _write_text(assets_dir / f"{aid}_negative.txt", neg)
    if not motion_pack:
        return
    _write_text(prompts / "film_motion.txt", motion_pack["film_motion_prompt"])
    _write_text(prompts / "motion_guide.md", motion_pack["guide_md"])
    for row in motion_pack["shots"]:
        sid = row["id"]
        _write_text(prompts / f"{sid}_motion.txt", row["motion_prompt"])
        _write_json(prompts / f"{sid}_motion.json", row["motion_json"])
        for tool_id, text in (row.get("by_tool") or {}).items():
            tool_dir = prompts / "tools" / tool_id
            _write_text(tool_dir / f"{sid}.txt", text)


def _export_remotion(
    spec: StudioSpec,
    compiled: Any,
    root: Path,
    *,
    character_path: str | None,
) -> None:
    from tools.remotion_emitter import write_story_composition_props

    eng = root / "engines" / "remotion"
    eng.mkdir(parents=True, exist_ok=True)
    write_story_composition_props(
        eng,
        storyboard=compiled.storyboard,
        cinematography=compiled.cinematography,
        timing=compiled.timing,
        continuity=compiled.continuity,
        style_profile={
            "style_id": spec.style_id,
            "grade": spec.grade,
            "pace": spec.pace,
            "emotion": spec.emotion,
        },
        character_path=character_path,
        title=spec.title,
        sync_remotion_public=False,
    )
    if character_path and Path(character_path).is_file():
        assets = eng / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        dest = assets / "character.png"
        shutil.copy2(character_path, dest)
    cloud_md = (
        "# Cloud / VPS render (Remotion)\n\n"
        "این پوشه فقط `story_props` + دارایی کاراکتر است.\n"
        "برای بستهٔ کامل (scaffold + props) از UI دکمهٔ **دانلود ZIP کلود** "
        "یا `tools.cloud_pack.build_cloud_render_zip` استفاده کنید.\n\n"
        "## پیش‌نیاز سرور\n"
        "Node.js 18+ · ۸ هسته · ۱۶GB RAM · بدون نیاز به GPU برای MVP\n\n"
        "## اجرا\n"
        "```bash\n"
        "cd remotion\n"
        "npm install\n"
        "npx remotion render src/index.ts StoryNarrative out/film.mp4 "
        "--props=./story_props.json\n"
        "```\n\n"
        "مستند CLI: https://www.remotion.dev/docs/cli/render\n"
    )
    _write_text(eng / "CLOUD_RENDER.md", cloud_md)
    _write_text(
        eng / "guide.md",
        "# موتور ویدیوی محلی (Remotion)\n\n"
        "## این کد چه می‌کند\n"
        "`story_props.json` تنظیمات ترکیب ویدیو است: شات‌ها، دوربین، rig، timing.\n\n"
        "## پیش‌نیاز\n"
        "Node.js · `cd remotion && npm install`\n\n"
        "## اجرا (خارج از Story)\n"
        "```bash\n"
        "cd remotion\n"
        "npx remotion render src/index.ts StoryNarrative out.mp4 "
        "--props=./story_props.json\n"
        "```\n\n"
        "جزئیات کلود: `CLOUD_RENDER.md`\n",
    )


def _export_slideshow(spec: StudioSpec, root: Path) -> None:
    eng = root / "engines" / "slideshow"
    eng.mkdir(parents=True, exist_ok=True)
    brief = spec.to_brief().replace('"""', '\\"\\"\\"')
    script = f'''#!/usr/bin/env python3
"""Run outside Story — builds slideshow MP4 from brief (Light path)."""
from pathlib import Path
from runtime.light_slideshow import render_from_prompt

BRIEF = """
{brief}
""".strip()

if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "output"
    out.mkdir(exist_ok=True)
    result = render_from_prompt(BRIEF, out_dir=out, seconds_per_slide=3.0)
    print("mp4:", result.get("render_mp4"))
'''
    _write_text(eng / "build.py", script)
    _write_text(
        eng / "guide.md",
        "# مسیر اسلاید ساده (Light)\n\n"
        "## این کد چه می‌کند\n"
        "`build.py` از متن brief اسلاید PNG می‌سازد و با FFmpeg MP4 encode می‌کند.\n\n"
        "## پیش‌نیاز\n"
        "Python · FFmpeg · `pip install -r requirements.txt`\n\n"
        "## اجرا\n"
        "```bash\n"
        "python engines/slideshow/build.py\n"
        "```\n",
    )


def spec_from_chain(
    chain: Any,
    *,
    title: str = "Story",
    quality: str = "light",
    runtime_seconds: float = 30.0,
    character_path: str | None = None,
    style_id: str = "symmetrical_pastel_cinema",
    grade: str = "pastel_muted",
    emotion: str = "neutral",
) -> StudioSpec:
    """Build StudioSpec from agent chain storyboard for export-only path."""
    shots: list[ShotControl] = []
    for sh in chain.storyboard.get("shots") or []:
        pose = sh.get("pose") or "idle"
        if pose not in {"idle", "walk", "react", "run"}:
            pose = "idle"
        beat = sh.get("story_beat") or "decision"
        if beat not in {
            "entrance",
            "reveal",
            "reaction",
            "conflict",
            "decision",
            "quiet_hold",
            "exit",
        }:
            beat = "decision"
        shots.append(
            ShotControl(
                title=str(sh.get("title") or ""),
                action=str(sh.get("action") or "Hold."),
                duration_sec=float(sh.get("duration_sec") or 3.0),
                pose=pose,  # type: ignore[arg-type]
                expression=str(sh.get("expression") or "neutral"),
                story_beat=beat,  # type: ignore[arg-type]
                dialogue=str(sh.get("dialogue") or ""),
            )
        )
    if not shots:
        shots = [ShotControl(action=title or "Story")]
    q = "pro" if str(quality).lower() == "pro" else "light"
    return StudioSpec(
        title=title,
        quality=q,  # type: ignore[arg-type]
        mode="agents",
        runtime_seconds=runtime_seconds,
        style_id=style_id,
        grade=grade,
        emotion=emotion,
        character_path=character_path,
        shots=shots,
    )


def export_animation_bundle(
    spec: StudioSpec,
    dest_dir: Path | str,
    *,
    targets: list[ExportTarget] | None = None,
    copy_character: bool = True,
) -> dict[str, Any]:
    """
    Write export bundle: screenplay, explanation, prompts, engine artifacts.

    Does not render video inside Story.
    """
    from tools.export_bundle_gate import run_export_bundle_gate, write_export_gate
    from tools.studio_api import compile_studio_spec, save_studio_spec

    root = Path(dest_dir)
    root.mkdir(parents=True, exist_ok=True)
    chosen = list(targets or DEFAULT_TARGETS)
    char = None
    if copy_character:
        char = spec.resolved_character()
        if spec.character_id:
            try:
                from tools.character_library import materialize_character_into_job

                meta = materialize_character_into_job(spec.character_id, root)
                char = meta.get("character_path") or char
            except Exception:  # noqa: BLE001
                pass
    compiled = compile_studio_spec(spec)
    agents_out = _run_export_agents(spec, compiled)
    try:
        from tools.director_ui_data import apply_prompt_overrides_to_agents, load_prompt_overrides

        job_root = root.parent if root.name == "export" else root
        ov = load_prompt_overrides(job_root)
        if ov:
            agents_out = apply_prompt_overrides_to_agents(agents_out, ov)
    except ImportError:
        pass

    save_studio_spec(spec, root / "studio_spec.json")
    _write_text(root / "screenplay.md", agents_out["screenplay"]["screenplay_md"])
    _write_json(root / "screenplay.json", agents_out["screenplay"])
    _write_text(root / "explanation.md", agents_out["notes"]["explanation_md"])

    if "prompts" in chosen:
        _export_prompts_from_agent(
            agents_out["prompts"], root, motion_pack=agents_out["motion"]
        )
    if "remotion" in chosen:
        _export_remotion(spec, compiled, root, character_path=char)
    if "slideshow" in chosen:
        _export_slideshow(spec, root)

    manifest = {
        "title": spec.title,
        "schema_version": spec.schema_version,
        "shot_count": len(spec.shots),
        "runtime_seconds": spec.runtime_seconds,
        "targets": chosen,
        "files": {
            "screenplay": "screenplay.md",
            "screenplay_json": "screenplay.json",
            "explanation": "explanation.md",
            "spec": "studio_spec.json",
            "export_gate": "export_gate.json",
        },
    }
    _write_json(root / "manifest.json", manifest)
    _write_text(
        root / "README.md",
        "# بستهٔ ساخت انیمیشن\n\n"
        "| فایل | نقش |\n|------|-----|\n"
        "| `screenplay.md` | نمایشنامه |\n"
        "| `screenplay.json` | نمایشنامه ساخت‌یافته |\n"
        "| `explanation.md` | توضیح زبان طبیعی |\n"
        "| `prompts/` | پرامپت تصویر + motion/I2V per-shot |\n"
        "| `engines/` | کد و راهنمای موتور مقصد |\n"
        "| `export_gate.json` | QA بسته قبل از خروج |\n"
        "| `style_recommendation.json` | پیشنهاد style از brief |\n"
        "| `studio_spec.json` | مشخصات فنی (منبع حقیقت) |\n\n"
        "Story عکس/ویدیو نمی‌سازد — رندر در ابزار خارجی.\n",
    )

    from agents.style_recommender_agent import recommend_styles

    brief_text = spec.to_brief()
    style_rec = recommend_styles(
        brief_text,
        emotion=spec.emotion,
        current_style_id=spec.style_id,
    )
    _write_json(root / "style_recommendation.json", style_rec)

    gate = run_export_bundle_gate(root, targets=chosen)
    write_export_gate(root, gate)
    manifest["export_gate_ok"] = gate["ok"]
    _write_json(root / "manifest.json", manifest)

    if not gate["ok"]:
        return {
            "ok": False,
            "error": f"export gate failed: {gate['missing']}",
            "export_root": str(root.resolve()),
            "gate": gate,
        }

    return {
        "ok": True,
        "export_root": str(root.resolve()),
        "manifest": str((root / "manifest.json").resolve()),
        "screenplay": str((root / "screenplay.md").resolve()),
        "explanation": str((root / "explanation.md").resolve()),
        "targets": chosen,
    }
