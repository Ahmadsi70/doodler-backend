"""CLI: ``story-studio`` / ``python story_cli.py`` / ``python __main__.py``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Story — animation construction export studio")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ready = sub.add_parser("ready", help="Print readiness probe JSON")
    p_ready.set_defaults(fn="ready")

    p_run = sub.add_parser(
        "render",
        help="Export bundle OR render to MP4 (use --do-render for direct MP4 output)",
    )
    p_run.add_argument("--spec", "-s", default="", help="StudioSpec JSON path")
    p_run.add_argument("--brief", "-b", default="", help="Free-text brief (agent path)")
    p_run.add_argument("--quality", "-q", default="light", choices=["light", "pro"])
    p_run.add_argument("--style-id", default="")
    p_run.add_argument("--character", default="", help="Main character image path")
    p_run.add_argument("--emotion", default="neutral")
    p_run.add_argument("--use-llm", action="store_true")
    p_run.add_argument("--seconds", type=float, default=60.0)
    p_run.add_argument("--job-id", default="")
    p_run.add_argument("--do-render", action="store_true", help="Render MP4 directly (not just export)")
    p_run.add_argument(
        "--write-example-spec",
        default="",
        help="Write example StudioSpec JSON to path and exit",
    )
    p_run.set_defaults(fn="render")

    p_exp2 = sub.add_parser(
        "export",
        help="Export screenplay, prompts, and engine code (add --render for MP4)",
    )
    p_exp2.add_argument("--spec", "-s", default="", help="StudioSpec JSON path")
    p_exp2.add_argument("--brief", "-b", default="", help="Free-text brief (agent path)")
    p_exp2.add_argument("--quality", "-q", default="light", choices=["light", "pro"])
    p_exp2.add_argument("--character", default="", help="Main character image path")
    p_exp2.add_argument("--use-llm", action="store_true")
    p_exp2.add_argument("--seconds", type=float, default=60.0)
    p_exp2.add_argument("--job-id", default="")
    p_exp2.add_argument("--out", "-o", default="", help="Output job directory")
    p_exp2.add_argument(
        "--targets",
        default="",
        help="Comma engines: prompts,remotion,slideshow",
    )
    p_exp2.add_argument(
        "--export-level",
        default="full",
        choices=["lightweight", "full", "rendering"],
        help="Export detail level: lightweight (fast), full (all artifacts), rendering (render-only)",
    )
    p_exp2.add_argument("--render", action="store_true", help="Render MP4 after export (Phase E)")
    p_exp2.add_argument(
        "--code-only", action="store_true",
        help="Generate ready-to-run render scripts instead of MP4",
    )
    p_exp2.set_defaults(fn="export")

    p_exp = sub.add_parser(
        "pack-export",
        help="Export portable pack (spec + assets) to share with others",
    )
    p_exp.add_argument("--spec", "-s", required=True, help="Source StudioSpec JSON")
    p_exp.add_argument("--out", "-o", required=True, help="Output pack directory")
    p_exp.add_argument("--character", default="", help="Character image to embed")
    p_exp.add_argument("--pack-id", default="story_pack")
    p_exp.add_argument("--from-job", default="", help="Optional job dir with studio_spec.json")
    p_exp.set_defaults(fn="pack_export")

    p_pr = sub.add_parser(
        "pack-render",
        help="(alias) Export from pack directory — no video",
    )
    p_pr.add_argument("--pack", "-p", required=True, help="Pack directory")
    p_pr.add_argument("--quality", "-q", default="pro", choices=["light", "pro"])
    p_pr.add_argument("--character", default="", help="Override character for this run")
    p_pr.add_argument("--job-id", default="")
    p_pr.set_defaults(fn="pack_render")

    p_sw = sub.add_parser(
        "pack-swap",
        help="Replace assets/character.png inside an existing pack",
    )
    p_sw.add_argument("--pack", "-p", required=True)
    p_sw.add_argument("--character", "-c", required=True)
    p_sw.set_defaults(fn="pack_swap")

    p_des = sub.add_parser(
        "design",
        help="Director design only (no video) → preview + downloadable Spec",
    )
    p_des.add_argument("--brief", "-b", required=True)
    p_des.add_argument("--out", "-o", required=True, help="Job/design output directory")
    p_des.add_argument("--quality", "-q", default="light", choices=["light", "pro"])
    p_des.add_argument("--seconds", type=float, default=60.0)
    p_des.add_argument("--character", default="")
    p_des.add_argument("--use-llm", action="store_true")
    p_des.set_defaults(fn="design")

    p_rev = sub.add_parser("revise", help="Patch design with a revise prompt")
    p_rev.add_argument("--job", "-j", required=True, help="Design job directory")
    p_rev.add_argument("--prompt", "-p", required=True)
    p_rev.add_argument("--shots", default="", help="Comma indices e.g. 0,2")
    p_rev.set_defaults(fn="revise")

    p_ap = sub.add_parser(
        "approve-render",
        help="Approve design (optional) and/or export bundle if approved",
    )
    p_ap.add_argument("--job", "-j", required=True)
    p_ap.add_argument("--approve-only", action="store_true")
    p_ap.add_argument("--render", action="store_true", help="Export after approve (alias)")
    p_ap.add_argument(
        "--by-acts",
        action="store_true",
        help="(ignored) legacy flag — export is always full bundle",
    )
    p_ap.set_defaults(fn="approve_render")

    p_ronly = sub.add_parser(
        "render-only",
        help="Render MP4 from existing export or spec (skip agents)",
    )
    p_ronly.add_argument("--export-dir", default="", help="Path to export directory with story_props.json")
    p_ronly.add_argument("--spec", "-s", default="", help="StudioSpec JSON — auto-exports then renders")
    p_ronly.add_argument("--quality", "-q", default="pro", choices=["light", "pro"])
    p_ronly.add_argument("--code-only", action="store_true", help="Generate render scripts instead of MP4")
    p_ronly.set_defaults(fn="render_only")

    p_doodle = sub.add_parser(
        "doodle",
        help="Run the DoodlerGAN + Animated Drawings pipeline",
    )
    p_doodle.add_argument("--brief", "-b", required=True, help="Sketch brief / idea")
    p_doodle.add_argument("--out", "-o", default="out/doodle_job", help="Output directory")
    p_doodle.set_defaults(fn="doodle")

    args = parser.parse_args(argv)

    from tools.job_workspace import new_job_id
    from tools.story_pipeline import readiness_probe, run_story_job

    if args.fn == "ready":
        probe = readiness_probe()
        print(json.dumps(probe, indent=2, ensure_ascii=False))
        return 0 if probe.get("ok") else 1

    if args.fn == "doodle":
        from doodler_pipeline import run_doodle_pipeline
        run_doodle_pipeline(args.brief, args.out)
        return 0

    if args.fn == "export":
        from tools.studio_api import export_from_spec, load_studio_spec

        targets = [t.strip() for t in (args.targets or "").split(",") if t.strip()] or None
        do_render = bool(getattr(args, "render", False))
        code_only = bool(getattr(args, "code_only", False))

        def on_event_export(kind: str, payload) -> None:
            if kind in {"phase", "log"}:
                print(f"[{kind}] {payload}", flush=True)

        if (args.spec or "").strip():
            spec = load_studio_spec(args.spec.strip())
            if args.quality:
                spec = spec.model_copy(update={"quality": args.quality})
            if args.character.strip():
                spec = spec.model_copy(
                    update={"character_path": str(Path(args.character).resolve())}
                )
            job_id = (args.job_id or "").strip() or new_job_id()
            ws = Path(args.out).resolve() if (args.out or "").strip() else None
            result = export_from_spec(
                spec,
                job_id=job_id,
                workspace=ws,
                on_event=on_event_export,
                targets=targets,
                render=do_render,
                render_mode="code_only" if code_only else "direct_render",
            )
        elif (args.brief or "").strip():
            job_id = (args.job_id or "").strip() or new_job_id()
            extras = {
                "quality": args.quality,
                "runtime_seconds": args.seconds,
                "use_llm": bool(args.use_llm),
                "render": do_render,
                "render_mode": "code_only" if code_only else "direct_render",
            }
            if args.character.strip():
                extras["character_path"] = str(Path(args.character).resolve())
            result = run_story_job(
                args.brief.strip(), job_id, extras, on_event=on_event_export
            )
        else:
            print("error: export needs --spec or --brief", file=sys.stderr)
            return 2
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        art = result.get("artifacts") or {}
        render_ok = (art.get("render") or {}).get("ok")
        if do_render and not render_ok:
            render_err = (art.get("render") or {}).get("error") or "render failed"
            print(f"render error: {render_err}", file=sys.stderr)
            return 2
        return 0 if result.get("ok") and art.get("export_root") else 2

    if args.fn == "pack_export":
        from tools.studio_api import load_studio_spec
        from tools.story_pack import export_pack_from_job, export_story_pack

        if (args.from_job or "").strip():
            out = export_pack_from_job(args.from_job.strip(), args.out)
        else:
            spec = load_studio_spec(args.spec)
            if args.character.strip():
                spec = spec.model_copy(
                    update={"character_path": str(Path(args.character).resolve())}
                )
            out = export_story_pack(
                spec, args.out, pack_id=(args.pack_id or "story_pack").strip()
            )
        print(json.dumps({"pack": str(out)}, indent=2, ensure_ascii=False))
        return 0

    if args.fn == "pack_swap":
        from tools.story_pack import swap_pack_character

        dest = swap_pack_character(args.pack, args.character)
        print(json.dumps({"character": str(dest)}, indent=2))
        return 0

    if args.fn == "pack_render":
        from tools.studio_api import render_from_spec
        from tools.story_pack import load_pack_spec, swap_pack_character

        pack = Path(args.pack)
        if args.character.strip():
            swap_pack_character(pack, args.character.strip())
        spec = load_pack_spec(pack)
        spec = spec.model_copy(update={"quality": args.quality, "mode": "direct"})

        def on_event_pack(kind: str, payload) -> None:
            if kind in {"phase", "log"}:
                print(f"[{kind}] {payload}", flush=True)

        job_id = (args.job_id or "").strip() or new_job_id()
        result = render_from_spec(spec, job_id=job_id, on_event=on_event_pack)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 0 if result.get("ok") else 2

    if args.fn == "design":
        from tools.director_board import design_from_brief

        out = Path(args.out)
        board = design_from_brief(
            args.brief,
            job_dir=out,
            quality=args.quality,
            runtime_seconds=float(args.seconds),
            character_path=str(Path(args.character).resolve())
            if args.character.strip()
            else None,
            use_llm=bool(args.use_llm),
        )
        print(
            json.dumps(
                {
                    "status": board.status,
                    "approved": board.approved,
                    "shots": len(board.spec.shots),
                    "preview": str(out / "design" / "design_preview.md"),
                    "spec": str(out / "studio_spec.json"),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if args.fn == "revise":
        from tools.director_board import load_board, revise_design

        job = Path(args.job)
        board = load_board(job)
        shots = None
        if (args.shots or "").strip():
            shots = [int(x) for x in args.shots.split(",") if x.strip() != ""]
        board = revise_design(board, args.prompt, shot_indices=shots, job_dir=job)
        print(
            json.dumps(
                {
                    "revision_count": board.revision_count,
                    "approved": board.approved,
                    "notes": board.notes[-6:],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if args.fn == "approve_render":
        from tools.director_board import approve_design, load_board, render_approved_design

        job = Path(args.job)
        board = load_board(job)
        if args.approve_only or args.render or not board.approved:
            board = approve_design(board, job_dir=job)
        if args.approve_only and not args.render:
            print(json.dumps({"approved": True, "status": board.status}, indent=2))
            return 0
        result = render_approved_design(
            board, job_dir=job, by_acts=bool(getattr(args, "by_acts", False))
        )
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 0 if result.get("ok") else 2

    if args.fn == "render_only":
        code_only = bool(getattr(args, "code_only", False))
        mode = "code_only" if code_only else "direct_render"

        if (args.export_dir or "").strip():
            from agents.render_agent import run_render_agent

            exp = Path(args.export_dir.strip())
            result = run_render_agent(
                exp,
                mode=mode,
                quality=args.quality,
            )
            print(json.dumps({
                "ok": result.ok,
                "backend": result.backend,
                "render_mp4": result.render_mp4,
                "code_dir": result.code_dir,
                "code_files": result.code_files,
                "run_command": result.run_command,
                "error": result.error,
                "logs": result.logs,
            }, indent=2, ensure_ascii=False, default=str))
            return 0 if result.ok else 2

        if (args.spec or "").strip():
            from agents.render_agent import render_from_studio_spec

            result = render_from_studio_spec(
                args.spec.strip(),
                Path(args.spec.strip()).parent / "render_out",
                mode=mode,
                quality=args.quality,
            )
            print(json.dumps({
                "ok": result.ok,
                "backend": result.backend,
                "render_mp4": result.render_mp4,
                "code_dir": result.code_dir,
                "code_files": result.code_files,
                "run_command": result.run_command,
                "error": result.error,
                "logs": result.logs,
            }, indent=2, ensure_ascii=False, default=str))
            return 0 if result.ok else 2

        print("error: render-only needs --export-dir or --spec", file=sys.stderr)
        return 2

    # render
    if (args.write_example_spec or "").strip():
        from tools.studio_api import write_studio_spec_example

        path = write_studio_spec_example(args.write_example_spec.strip())
        print(json.dumps({"wrote": str(path)}, indent=2))
        return 0

    do_render = bool(getattr(args, "do_render", False))

    def on_event(kind: str, payload) -> None:
        if kind in {"phase", "log"}:
            print(f"[{kind}] {payload}", flush=True)

    if (args.spec or "").strip():
        from tools.studio_api import load_studio_spec, render_from_spec

        spec = load_studio_spec(args.spec.strip())
        if args.quality:
            spec = spec.model_copy(update={"quality": args.quality})
        if args.character.strip():
            spec = spec.model_copy(
                update={"character_path": str(Path(args.character).resolve())}
            )
        if args.style_id:
            spec = spec.model_copy(update={"style_id": args.style_id})
        job_id = (args.job_id or "").strip() or new_job_id()
        result = render_from_spec(spec, job_id=job_id, on_event=on_event, render=do_render)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        art = result.get("artifacts") or {}
        render_ok = (art.get("render") or {}).get("ok")
        if do_render and not render_ok:
            render_err = (art.get("render") or {}).get("error") or "render failed"
            print(f"render error: {render_err}", file=sys.stderr)
            return 2
        return 0 if result.get("ok") and art.get("export_root") else 2

    if not (args.brief or "").strip():
        print(
            "error: provide --spec / --brief, or use pack-export / pack-render\n"
            "hint: python __main__.py render --write-example-spec examples/studio_spec.json",
            file=sys.stderr,
        )
        return 2

    job_id = (args.job_id or "").strip() or new_job_id()
    extras: dict = {
        "quality": args.quality,
        "runtime_seconds": args.seconds,
        "use_llm": bool(args.use_llm),
        "emotion": (args.emotion or "neutral").strip() or "neutral",
        "render": do_render,
    }
    if args.style_id:
        extras["style_id"] = args.style_id
    if args.character.strip():
        extras["character_path"] = str(Path(args.character).resolve())

    result = run_story_job(args.brief, job_id, extras, on_event=on_event)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    art = result.get("artifacts") or {}
    render_ok = (art.get("render") or {}).get("ok")
    if do_render and not render_ok:
        render_err = (art.get("render") or {}).get("error") or "render failed"
        print(f"render error: {render_err}", file=sys.stderr)
        return 2
    return 0 if art.get("export_root") else 2


if __name__ == "__main__":
    raise SystemExit(main())
