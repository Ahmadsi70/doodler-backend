"""
RenderAgent — Phase E: output ready-to-run engine code or render directly to MP4.

Why: Story is a construction studio; users need a clear path from export artifacts
to a viewable video. This agent bridges the gap between "instruction set" and
"watchable result" — either by generating executable code or by invoking the
render engine directly.

Two modes:
  - **code-only**: Write ready-to-run scripts/code that the user can inspect and execute
  - **direct-render**: Invoke Remotion / FFmpeg immediately and return the MP4 path
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

RenderMode = Literal["code_only", "direct_render"]
RenderBackend = Literal["remotion", "ffmpeg_slideshow", "code_remotion", "code_slideshow"]


@dataclass
class RenderResult:
    """Structured output from RenderAgent."""

    ok: bool
    backend: RenderBackend = "code_remotion"
    render_mp4: str | None = None
    code_dir: str | None = None
    code_files: list[str] = field(default_factory=list)
    run_command: str | None = None
    error: str | None = None
    logs: list[str] = field(default_factory=list)


_ROOT = Path(__file__).resolve().parents[1]
_REMOTION = _ROOT / "remotion"


# ── helpers ──────────────────────────────────────────────────────────


def _remotion_ready() -> bool:
    return (_REMOTION / "node_modules" / "remotion").is_dir() and (
        _REMOTION / "package.json"
    ).is_file()


def _resolve_remotion_cli() -> list[str]:
    """Resolve Remotion CLI for subprocess (Windows support)."""
    bin_dir = _REMOTION / "node_modules" / ".bin"
    for name in ("remotion.cmd", "remotion"):
        local = bin_dir / name
        if local.is_file():
            return [str(local)]
    for name in ("npx.cmd", "npx"):
        found = shutil.which(name)
        if found:
            return [found, "--yes", "remotion"]
    cli_js = _REMOTION / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
    node = shutil.which("node")
    if node and cli_js.is_file():
        return [node, str(cli_js)]
    raise RuntimeError(
        "Remotion CLI not found. cd remotion && npm install"
    )


def _find_ffmpeg() -> str | None:
    for name in ("ffmpeg", "ffmpeg.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


# ── code generators ──────────────────────────────────────────────────


def _generate_remotion_code(
    props_path: Path,
    code_dir: Path,
    *,
    composition_id: str = "StoryNarrative",
    title: str = "Story",
) -> list[str]:
    """Generate ready-to-run Remotion render scripts (PowerShell + Bash)."""
    code_dir.mkdir(parents=True, exist_ok=True)
    files: list[str] = []

    props_abs = props_path.resolve()
    out_mp4 = (code_dir / "render.mp4").resolve()

    # PowerShell script
    ps1 = code_dir / "render.ps1"
    ps1_content = f"""# Render {title} with Remotion
# Requirements: cd remotion && npm install

$ErrorActionPreference = "Stop"
Push-Location "{_REMOTION.resolve()}"

npx remotion render {composition_id} "{out_mp4}" --props "{props_abs}"

if ($LASTEXITCODE -ne 0) {{
    Write-Error "Remotion render failed (code=$LASTEXITCODE)"
    Pop-Location
    exit 1
}}

Write-Host "✓ Rendered: {out_mp4}"
Pop-Location
"""
    ps1.write_text(ps1_content, encoding="utf-8")
    files.append(str(ps1))

    # Bash script
    sh_script = code_dir / "render.sh"
    sh_content = f"""#!/usr/bin/env bash
# Render {title} with Remotion
# Requirements: cd remotion && npm install
set -euo pipefail

cd "{_REMOTION.resolve()}"

npx remotion render {composition_id} "{out_mp4}" --props "{props_abs}"

echo "✓ Rendered: {out_mp4}"
"""
    sh_script.write_text(sh_content, encoding="utf-8")
    sh_script.chmod(0o755)
    files.append(str(sh_script))

    # README with manual instructions
    readme = code_dir / "RENDER_README.md"
    readme_content = f"""# Render {title}

## Quick render (PowerShell)
```powershell
.\\render.ps1
```

## Quick render (Bash)
```bash
./render.sh
```

## Manual render
```bash
cd {_REMOTION.resolve()}
npx remotion render {composition_id} "{out_mp4}" --props "{props_abs}"
```

## Requirements
- Node.js installed
- `cd remotion && npm install`
"""
    readme.write_text(readme_content, encoding="utf-8")
    files.append(str(readme))

    return files


def _generate_slideshow_code(
    props_path: Path,
    code_dir: Path,
    *,
    title: str = "Story",
) -> list[str]:
    """Generate ready-to-run FFmpeg slideshow script."""
    code_dir.mkdir(parents=True, exist_ok=True)
    files: list[str] = []

    ffmpeg = _find_ffmpeg()
    ffmpeg_cmd = ffmpeg or "ffmpeg"

    props_abs = props_path.resolve()
    out_mp4 = (code_dir / "render.mp4").resolve()

    # PowerShell — use Story's light render path
    ps1 = code_dir / "render_light.ps1"
    ps1_content = f"""# Render {title} — Light slideshow via Story pipeline
$ErrorActionPreference = "Stop"
Push-Location "{_ROOT.resolve()}"

python -c @"
from pathlib import Path
from tools.remotion_emitter import render_story
import json

props = json.loads(Path(r'{props_abs}').read_text(encoding='utf-8'))
brief = props.get('title', 'Story')
result = render_story(
    brief=brief,
    out_dir=Path(r'{code_dir.resolve()}'),
    quality='light',
    storyboard=props,
    ffmpeg=r'{ffmpeg_cmd}',
)
print(json.dumps(result, indent=2, ensure_ascii=False))
"@

Pop-Location
Write-Host "✓ Slideshow rendered: {out_mp4}"
"""
    ps1.write_text(ps1_content, encoding="utf-8")
    files.append(str(ps1))

    # README
    readme = code_dir / "RENDER_README.md"
    readme_content = f"""# Render {title} — Light Slideshow

## Quick render
```powershell
.\\render_light.ps1
```

## Requirements
- FFmpeg on PATH
- Python 3.11+

Output: `{out_mp4}`
"""
    readme.write_text(readme_content, encoding="utf-8")
    files.append(str(readme))

    return files


# ── render agent ─────────────────────────────────────────────────────


def run_render_agent(
    export_dir: Path | str,
    *,
    mode: RenderMode = "code_only",
    quality: str = "light",
    composition_id: str = "StoryNarrative",
    title: str = "Story",
    timeout_sec: float = 900.0,
    prefer_backend: RenderBackend | None = None,
) -> RenderResult:
    """
    Phase E render agent — decide render path and execute.

    Args:
        export_dir: Path to export bundle (contains story_props.json)
        mode: 'code_only' → generate scripts; 'direct_render' → render MP4 now
        quality: 'light' or 'pro'
        composition_id: Remotion composition name
        title: Film title for generated code
        timeout_sec: Timeout for direct render
        prefer_backend: Force a specific backend (optional)

    Returns:
        RenderResult with status, paths, and generated artifacts
    """
    exp = Path(export_dir)
    logs: list[str] = []

    # Locate story props
    props_path = exp / "story_props.json"
    if not props_path.is_file():
        # Try remotion/public
        alt = _REMOTION / "public" / "story_props.json"
        if alt.is_file():
            props_path = alt
        else:
            return RenderResult(
                ok=False,
                error=f"story_props.json not found in {exp}",
                logs=logs,
            )

    # Decide backend
    if prefer_backend:
        backend: RenderBackend = prefer_backend
    elif quality == "pro" and _remotion_ready():
        backend = "remotion" if mode == "direct_render" else "code_remotion"
    elif _remotion_ready():
        backend = "remotion" if mode == "direct_render" else "code_remotion"
    elif _find_ffmpeg():
        backend = "ffmpeg_slideshow" if mode == "direct_render" else "code_slideshow"
    else:
        # No engines available — output code only with instructions
        backend = "code_slideshow"

    logs.append(f"render_agent mode={mode} quality={quality} backend={backend}")

    # ── Code-only mode ──
    if mode == "code_only":
        code_dir = exp / "render_code"
        code_dir.mkdir(parents=True, exist_ok=True)

        if backend in ("code_remotion", "remotion"):
            files = _generate_remotion_code(
                props_path, code_dir,
                composition_id=composition_id,
                title=title,
            )
            run_cmd = f"cd {_REMOTION.resolve()} && npx remotion render {composition_id} render.mp4 --props {props_path.resolve()}"

            # Also copy story_props.json into code dir for standalone use
            shutil.copy2(props_path, code_dir / "story_props.json")
        else:
            files = _generate_slideshow_code(
                props_path, code_dir,
                title=title,
            )
            run_cmd = f"powershell {code_dir / 'render_light.ps1'}"

        logs.append(f"code_only: {len(files)} files in {code_dir}")
        return RenderResult(
            ok=True,
            backend=backend,
            code_dir=str(code_dir.resolve()),
            code_files=files,
            run_command=run_cmd,
            logs=logs,
        )

    # ── Direct render mode ──
    if backend == "remotion":
        return _direct_render_remotion(
            props_path, exp, composition_id=composition_id,
            timeout_sec=timeout_sec, logs=logs,
        )
    else:
        return _direct_render_slideshow(
            props_path, exp, quality=quality, logs=logs,
        )


def _direct_render_remotion(
    props_path: Path,
    out_dir: Path,
    *,
    composition_id: str,
    timeout_sec: float,
    logs: list[str],
) -> RenderResult:
    """Invoke Remotion render subprocess directly."""
    if not _remotion_ready():
        return RenderResult(
            ok=False,
            error="Remotion not installed. cd remotion && npm install",
            backend="remotion",
            logs=logs,
        )

    dest = out_dir / "render.mp4"
    cmd = [
        *_resolve_remotion_cli(),
        "render",
        composition_id,
        str(dest.resolve()),
        "--props",
        str(props_path.resolve()),
        "--log",
        "error",
    ]
    env = os.environ.copy()
    log_path = out_dir / "remotion_render.log"

    logs.append(f"remotion render: {' '.join(cmd)}")

    try:
        with log_path.open("w", encoding="utf-8") as log_f:
            log_f.write("CMD: " + " ".join(cmd) + "\n\n")
            log_f.flush()
            proc = subprocess.run(
                cmd,
                cwd=str(_REMOTION),
                stdout=log_f,
                stderr=subprocess.STDOUT,
                env=env,
                timeout=timeout_sec,
                shell=False,
            )
    except subprocess.TimeoutExpired:
        return RenderResult(
            ok=False,
            error=f"Remotion render timed out after {timeout_sec}s",
            backend="remotion",
            logs=logs,
        )

    if proc.returncode != 0 or not dest.is_file() or dest.stat().st_size <= 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-2500:]
        return RenderResult(
            ok=False,
            error=f"Remotion failed (code={proc.returncode}):\n{tail}",
            backend="remotion",
            logs=logs,
        )

    logs.append(f"remotion render OK → {dest.resolve()}")
    return RenderResult(
        ok=True,
        backend="remotion",
        render_mp4=str(dest.resolve()),
        logs=logs,
    )


def _direct_render_slideshow(
    props_path: Path,
    out_dir: Path,
    *,
    quality: str,
    logs: list[str],
) -> RenderResult:
    """Render via Story's light slideshow pipeline (FFmpeg)."""
    try:
        from tools.studio_profiles import find_ffmpeg
    except ImportError:
        from ..tools.studio_profiles import find_ffmpeg

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return RenderResult(
            ok=False,
            error="FFmpeg not found on PATH. Install FFmpeg for light rendering.",
            backend="ffmpeg_slideshow",
            logs=logs,
        )

    try:
        from runtime.light_slideshow import render_from_prompt
    except ImportError:
        from ..runtime.light_slideshow import render_from_prompt

    # Build brief from props
    try:
        props = json.loads(props_path.read_text(encoding="utf-8"))
    except Exception:
        props = {}
    shots = props.get("shots") or []
    brief = "\n\n".join(
        f"{s.get('title', '')}\n{s.get('action', '')}".strip()
        for s in shots
    ) or props.get("title", "Story")

    logs.append(f"slideshow render: {len(shots)} shots, ffmpeg={ffmpeg}")

    try:
        art = render_from_prompt(
            brief,
            str(out_dir),
            ffmpeg=str(ffmpeg),
            quality=quality if quality in {"light", "pro"} else "light",
            studio="story",
        )
    except Exception as exc:
        return RenderResult(
            ok=False,
            error=f"Slideshow render failed: {exc}",
            backend="ffmpeg_slideshow",
            logs=logs,
        )

    mp4 = art.get("render_mp4") or ""
    ok = bool(art.get("ok")) and Path(mp4).is_file()
    logs.append(f"slideshow render {'OK' if ok else 'FAILED'} → {mp4}")
    return RenderResult(
        ok=ok,
        backend="ffmpeg_slideshow",
        render_mp4=str(mp4) if ok else None,
        error=None if ok else f"Slideshow produced no MP4: {art}",
        logs=logs,
    )


# ── convenience: render from StudioSpec directly ─────────────────────


def render_from_studio_spec(
    spec_path: Path | str,
    out_dir: Path | str,
    *,
    mode: RenderMode = "direct_render",
    quality: str = "pro",
    timeout_sec: float = 900.0,
) -> RenderResult:
    """
    High-level: load a StudioSpec, export it, then render.

    This is the end-to-end path for "give me a spec, I'll give you an MP4."
    """
    from tools.studio_api import load_studio_spec, compile_studio_spec
    from tools.remotion_emitter import write_story_composition_props

    spec = load_studio_spec(spec_path)
    compiled = compile_studio_spec(spec)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Save spec for traceability
    from tools.studio_api import save_studio_spec
    save_studio_spec(spec, out / "studio_spec.json")

    # Write story props
    _ = write_story_composition_props(
        out,
        storyboard=compiled.storyboard,
        cinematography=compiled.cinematography,
        timing=compiled.timing,
        continuity=compiled.continuity,
        title=spec.title or "Story",
        character_path=spec.character_path,
    )

    return run_render_agent(
        out,
        mode=mode,
        quality=quality or spec.quality or "pro",
        title=spec.title or "Story",
        timeout_sec=timeout_sec,
    )
