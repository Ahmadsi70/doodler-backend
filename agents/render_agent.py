"""
RenderAgent — generates code the user can run to produce the final animation.

Only ``code_only`` mode is kept; direct MP4 rendering is removed because
this project delivers Remotion code (not video) as its output.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

RenderMode = Literal["code_only"]
RenderBackend = Literal["code_remotion", "code_slideshow"]


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


# ── render agent ─────────────────────────────────────────────────────


def run_render_agent(
    export_dir: Path | str,
    *,
    mode: RenderMode = "code_only",
    title: str = "Story",
    composition_id: str = "StoryNarrative",
) -> RenderResult:
    """Generate runnable Remotion render scripts from exported specs (code-only)."""
    exp = Path(export_dir)
    logs: list[str] = []

    props_path = exp / "story_props.json"
    if not props_path.is_file():
        alt = exp / "engines" / "remotion" / "story_props.json"
        if alt.is_file():
            props_path = alt
        else:
            alt2 = _REMOTION / "public" / "story_props.json"
            if alt2.is_file():
                props_path = alt2
            else:
                return RenderResult(
                    ok=False,
                    error=f"story_props.json not found in {exp}",
                    logs=logs,
                )

    code_dir = exp / "render_code"
    code_dir.mkdir(parents=True, exist_ok=True)

    files = _generate_remotion_code(
        props_path, code_dir,
        composition_id=composition_id,
        title=title,
    )
    shutil.copy2(props_path, code_dir / "story_props.json")

    logs.append(f"code_only: {len(files)} files in {code_dir}")
    return RenderResult(
        ok=True,
        backend="code_remotion",
        code_dir=str(code_dir.resolve()),
        code_files=files,
        run_command=f"cd {_REMOTION.resolve()} && npx remotion render {composition_id} render.mp4 --props {props_path.resolve()}",
        logs=logs,
    )
