"""Story has no Manim path — use export + external engines."""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "Story export-only studio.\n"
        "Use: python scripts\\smoke_render.py\n"
        "Or:  python scripts\\smoke_remotion.py\n"
        "Or:  python __main__.py export --brief \"...\"",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
