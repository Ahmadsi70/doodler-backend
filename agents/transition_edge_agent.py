"""
TransitionEdgeAgent — cut edges with grammar + continuity safety.

Why: per-shot transitionIn was beat-pair only; flips of screen direction
need hard/match cuts without slide, and frames must fit destination length.
"""

from __future__ import annotations

from typing import Any

try:
    from tools.craft_packs import load_transition_grammar, resolve_transition
except ImportError:
    from ..tools.craft_packs import load_transition_grammar, resolve_transition  # type: ignore


def run_transition_edge_agent(
    shots: list[dict[str, Any]],
    *,
    continuity_graph: dict[str, Any] | None = None,
    fps: int = 24,
) -> dict[str, Any]:
    """
    Emit transition_edges#v1 for consecutive shot pairs.

    Clamps frames to ≤ floor(min(prev,dest)/3) and disables slide on risk edges.
    """
    grammar = load_transition_grammar()
    catalog = dict(grammar.get("transitions") or {})
    default_frames = int(grammar.get("default_frames") or 12)

    by_id: dict[Any, dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []
    for i, sh in enumerate(shots):
        sid = sh.get("shot_id", sh.get("shotId", i))
        row = {
            "shot_id": sid,
            "story_beat": str(
                sh.get("story_beat") or sh.get("storyBeat") or "decision"
            ),
            "duration_frames": int(
                sh.get("duration_frames")
                or sh.get("durationFrames")
                or max(12, round(float(sh.get("duration_sec") or 3) * fps))
            ),
        }
        by_id[sid] = row
        ordered.append(row)

    graph_edges = {
        (e.get("from"), e.get("to")): e
        for e in (continuity_graph or {}).get("edges") or []
        if isinstance(e, dict)
    }

    edges: list[dict[str, Any]] = []
    for a, b in zip(ordered, ordered[1:]):
        g = graph_edges.get((a["shot_id"], b["shot_id"])) or {}
        risk = g.get("risk")
        meta = resolve_transition(a["story_beat"], b["story_beat"])
        tid = str(g.get("transition") or meta.get("id") or "crossfade")
        if risk:
            tid = "hard_cut" if tid not in {"match_cut", "hard_cut"} else tid
        recipe = dict(catalog.get(tid) or meta or {})
        frames = int(recipe.get("frames") or meta.get("frames") or default_frames)
        max_frames = max(2, min(a["duration_frames"], b["duration_frames"]) // 3)
        frames = max(2, min(frames, max_frames))
        if risk:
            frames = min(frames, 4)
        opacity = bool(recipe.get("opacity", True))
        slide = bool(recipe.get("slide", tid == "crossfade"))
        if risk or tid in {"hard_cut", "match_cut", "hold_black"}:
            slide = False
        edges.append(
            {
                "from": a["shot_id"],
                "to": b["shot_id"],
                "id": tid,
                "frames": frames,
                "opacity": opacity,
                "slide": slide,
                "safe": risk is None,
                "risk": risk,
                "from_beat": a["story_beat"],
                "to_beat": b["story_beat"],
            }
        )

    return {
        "agent": "TransitionEdgeAgent",
        "schema": "transition_edges#v1",
        "fps": fps,
        "edges": edges,
        "notes": [f"edges={len(edges)}"],
    }


def transition_in_for_shot(
    edges: dict[str, Any] | None,
    shot_id: Any,
) -> dict[str, Any] | None:
    """Map destination shot_id → Remotion transitionIn payload."""
    if not edges:
        return None
    for e in edges.get("edges") or []:
        if e.get("to") == shot_id:
            return {
                "id": e.get("id") or "crossfade",
                "frames": int(e.get("frames") or 12),
                "opacity": bool(e.get("opacity", True)),
                "slide": bool(e.get("slide", True)),
            }
    return None
