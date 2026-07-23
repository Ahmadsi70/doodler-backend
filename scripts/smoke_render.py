"""Smoke: Story brief → export bundle (no in-tool video)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from tools.job_workspace import new_job_id
    from tools.story_pipeline import readiness_probe, run_story_job

    probe = readiness_probe()
    print(json.dumps(probe, indent=2))
    if not probe.get("ok"):
        return 1
    brief = (
        "A lonely character enters a quiet room.\n\n"
        "Then they notice a letter because sunlight hits the table.\n\n"
        "They step forward and breathe."
    )

    def on_event(kind: str, payload) -> None:
        if kind in {"phase", "log"}:
            try:
                print(f"[{kind}] {payload}", flush=True)
            except UnicodeEncodeError:
                print(f"[{kind}] {ascii(payload)}", flush=True)

    result = run_story_job(
        brief,
        new_job_id(),
        {"quality": "light", "runtime_seconds": 20, "use_llm": False, "ai_fill": False},
        on_event=on_event,
    )
    art = result.get("artifacts") or {}
    export_root = Path(str(art.get("export_root") or ""))
    screenplay = export_root / "screenplay.md"
    print("export_root=", export_root)
    print("screenplay=", screenplay.is_file())
    return 0 if export_root.is_dir() and screenplay.is_file() else 2


if __name__ == "__main__":
    raise SystemExit(main())
