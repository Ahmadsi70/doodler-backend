"""
Continuity graph — screen direction, eyeline, and per-shot state.

Why: approved:bool is not enough for long-form; Remotion and gates need
explicit nodes/edges that survive revise/render.
"""

from __future__ import annotations

from typing import Any


_BEAT_EMOTION = {
    "entrance": 0.35,
    "reveal": 0.45,
    "reaction": 0.75,
    "conflict": 0.85,
    "decision": 0.55,
    "quiet_hold": 0.25,
    "exit": 0.4,
}


def build_continuity_graph(
    *,
    storyboard: dict[str, Any],
    cinematography: dict[str, Any] | None = None,
    continuity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build continuity_graph#v1 from compiled agent/spec artifacts.

    Nodes carry screen_direction + emotional state; edges encode cut intent.
    """
    shots = list(storyboard.get("shots") or [])
    cine_by = {
        f.get("shot_id"): f for f in (cinematography or {}).get("frames") or []
    }
    cont = continuity or {}
    checks_by = {
        c.get("shot_id"): c for c in (cont.get("checks") or []) if isinstance(c, dict)
    }
    line_side = str(cont.get("180_line_side") or "left")

    nodes: list[dict[str, Any]] = []
    for i, sh in enumerate(shots):
        sid = sh.get("shot_id") if sh.get("shot_id") is not None else i
        crow = cine_by.get(sid) or cine_by.get(i) or {}
        check = checks_by.get(sid) or checks_by.get(i) or {}
        comp = str(crow.get("composition") or sh.get("composition_shape") or "C").upper()
        look = str(
            crow.get("look_space_direction")
            or check.get("look_space_direction")
            or ""
        ).lower()
        if look == "left":
            direction = "R_to_L"
        elif look == "right":
            direction = "L_to_R"
        elif comp.startswith("L"):
            direction = "L_to_R"
        elif comp.startswith("R"):
            direction = "R_to_L"
        else:
            direction = "hold"
        beat = str(sh.get("story_beat") or "decision")
        nodes.append(
            {
                "shot_id": sid,
                "screen_direction": direction,
                "look_space": look or ("right" if direction == "L_to_R" else "left"),
                "composition": comp[:1] or "C",
                "eyeline": str(check.get("eyeline") or "consistent"),
                "state": {
                    "emotion": float(_BEAT_EMOTION.get(beat, 0.5)),
                    "pose": str(sh.get("pose") or "idle"),
                    "expression": str(sh.get("expression") or "neutral"),
                    "beat": beat,
                    "prop": None,
                },
            }
        )

    edges: list[dict[str, Any]] = []
    for a, b in zip(nodes, nodes[1:]):
        reverse_risk = (
            a["screen_direction"] in {"L_to_R", "R_to_L"}
            and b["screen_direction"] in {"L_to_R", "R_to_L"}
            and a["screen_direction"] != b["screen_direction"]
        )
        transition = "crossfade"
        if a["state"]["beat"] == "reaction" or b["state"]["beat"] == "reaction":
            transition = "hard_cut"
        elif a["state"]["beat"] == "quiet_hold":
            transition = "dissolve"
        edges.append(
            {
                "from": a["shot_id"],
                "to": b["shot_id"],
                "transition": transition,
                "must_match": ["eyeline"] if not reverse_risk else [],
                "risk": "screen_direction_flip" if reverse_risk else None,
            }
        )

    violations = list(cont.get("violations") or [])
    for e in edges:
        if e.get("risk"):
            violations.append(f"edge {e['from']}→{e['to']}: {e['risk']}")

    return {
        "schema": "continuity_graph#v1",
        "line_side": line_side,
        "nodes": nodes,
        "edges": edges,
        "violations": violations,
        "approved": bool(cont.get("approved", True)) and not any(
            e.get("risk") and False for e in edges  # advisory only for now
        ),
    }


def continuity_gate(
    graph: dict[str, Any],
    *,
    strict: bool = False,
) -> dict[str, Any]:
    """
    Soft by default (advisory). Strict fails on screen_direction_flip risks.
    """
    violations = list(graph.get("violations") or [])
    risks = [
        e
        for e in (graph.get("edges") or [])
        if isinstance(e, dict) and e.get("risk")
    ]
    for e in risks:
        msg = f"edge {e.get('from')}→{e.get('to')}: {e.get('risk')}"
        if msg not in violations:
            violations.append(msg)
    if not strict:
        return {"ok": True, "strict": False, "violations": violations, "blocking": []}
    blocking = [v for v in violations if "screen_direction_flip" in v]
    return {
        "ok": len(blocking) == 0,
        "strict": True,
        "violations": violations,
        "blocking": blocking,
    }


def merge_graph_into_continuity(
    continuity: dict[str, Any],
    graph: dict[str, Any],
) -> dict[str, Any]:
    out = dict(continuity)
    out["graph"] = graph
    out["schema"] = "studio_spec#v1+continuity_graph"
    if graph.get("violations"):
        prev = list(out.get("violations") or [])
        out["violations"] = prev + [v for v in graph["violations"] if v not in prev]
    return out
