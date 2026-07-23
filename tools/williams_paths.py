"""
Resolve Williams package path (portable).

Why: Pro previously hard-depended on ``file:../../انیمیشن``. Operators can set
``WILLIAMS_RULES_PATH`` or drop a vendored copy under ``vendor/williams-animation-rules``.
"""

from __future__ import annotations

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def williams_rules_candidates() -> list[Path]:
    """Ordered candidate roots for williams-animation-rules."""
    out: list[Path] = []
    env = (os.environ.get("WILLIAMS_RULES_PATH") or "").strip()
    if env:
        out.append(Path(env).expanduser())
    out.append(_ROOT / "vendor" / "williams-animation-rules")
    # Legacy sibling install (optional)
    out.append(_ROOT.parent / "انیمیشن")
    return out


def resolve_williams_rules_path() -> Path | None:
    """Return first existing package root, else None."""
    for cand in williams_rules_candidates():
        pkg = cand / "package.json"
        if pkg.is_file():
            return cand.resolve()
        # Allow pointing directly at package.json parent already
        if cand.is_file() and cand.name == "package.json":
            return cand.parent.resolve()
    return None


def williams_ready() -> bool:
    return resolve_williams_rules_path() is not None


def williams_status() -> dict[str, object]:
    path = resolve_williams_rules_path()
    return {
        "ready": path is not None,
        "path": str(path) if path else None,
        "env_WILLIAMS_RULES_PATH": bool(
            (os.environ.get("WILLIAMS_RULES_PATH") or "").strip()
        ),
        "hint": "Set WILLIAMS_RULES_PATH or vendor/williams-animation-rules",
    }
