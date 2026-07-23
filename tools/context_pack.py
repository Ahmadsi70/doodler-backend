"""
Compressed context pack builder for act-scoped LLM / agent hops.

Why: SceneIR.compressed_context existed but was never filled; agents must see
bible + act summary + local shots only — not the whole film.
"""

from __future__ import annotations

from typing import Any

from scene_ir import CompressedContextLayer, CompressedContextPack
from studio_spec import StudioSpec

try:
    from tools.act_planner import ActSlice
except ImportError:
    from .act_planner import ActSlice  # type: ignore


def _approx_tokens(text: str) -> int:
    # Rough Latin/Persian heuristic: ~4 chars per token
    return max(1, (len(text) + 3) // 4) if text else 0


def _trim_to_budget(text: str, budget: int) -> str:
    if budget <= 0:
        return ""
    if _approx_tokens(text) <= budget:
        return text
    # Binary-ish trim by characters
    lo, hi = 0, len(text)
    best = ""
    while lo <= hi:
        mid = (lo + hi) // 2
        chunk = text[:mid].rstrip()
        if _approx_tokens(chunk) <= budget:
            best = chunk
            lo = mid + 1
        else:
            hi = mid - 1
    return best + ("…" if best and best != text else "")


def build_compressed_context(
    spec: StudioSpec,
    *,
    act: ActSlice,
    bible: str = "",
    prior_act_summaries: list[str] | None = None,
    token_budget: int | None = None,
    query: str = "",
) -> CompressedContextPack:
    """
    Four-layer pack under a hard token budget.

    essential  40% — bible + act goal
    relevant   35% — shots in this act only
    summary    15% — prior acts
    collaboration 10% — locks / notes
    """
    budget = int(token_budget or act.token_budget or 8000)
    budget = max(256, budget)
    pcts = {
        "essential": 0.40,
        "relevant": 0.35,
        "summary": 0.15,
        "collaboration": 0.10,
    }
    layer_budgets = {k: max(32, int(budget * v)) for k, v in pcts.items()}

    bible_text = (bible or spec.title or "Story").strip()
    essential_raw = (
        f"BIBLE: {bible_text}\n"
        f"ACT: {act.title} ({act.id})\n"
        f"GOAL: {act.summary}\n"
        f"SHOTS: {act.shot_start}..{act.shot_end - 1} "
        f"DUR={act.duration_sec:.1f}s"
    )
    essential = _trim_to_budget(essential_raw, layer_budgets["essential"])

    shot_lines: list[str] = []
    for i, sh in enumerate(spec.shots[act.shot_start : act.shot_end]):
        sid = act.shot_start + i
        shot_lines.append(
            f"[{sid}] {sh.story_beat}/{sh.pose}/{sh.camera}: {sh.action[:120]}"
        )
    relevant = _trim_to_budget("\n".join(shot_lines), layer_budgets["relevant"])

    prior = prior_act_summaries or []
    summary_raw = "PRIOR: " + (" | ".join(prior) if prior else "(none)")
    summary = _trim_to_budget(summary_raw, layer_budgets["summary"])

    collab_raw = (
        f"mode={spec.mode} quality={spec.quality} emotion={spec.emotion} "
        f"style={spec.style_id} notes={spec.notes[:200]}"
    )
    collaboration = _trim_to_budget(collab_raw, layer_budgets["collaboration"])

    layers = [
        CompressedContextLayer(
            name="essential",
            budget_pct=pcts["essential"],
            token_budget=layer_budgets["essential"],
            token_used=_approx_tokens(essential),
            content=essential,
        ),
        CompressedContextLayer(
            name="relevant",
            budget_pct=pcts["relevant"],
            token_budget=layer_budgets["relevant"],
            token_used=_approx_tokens(relevant),
            content=relevant,
        ),
        CompressedContextLayer(
            name="summary",
            budget_pct=pcts["summary"],
            token_budget=layer_budgets["summary"],
            token_used=_approx_tokens(summary),
            content=summary,
        ),
        CompressedContextLayer(
            name="collaboration",
            budget_pct=pcts["collaboration"],
            token_budget=layer_budgets["collaboration"],
            token_used=_approx_tokens(collaboration),
            content=collaboration,
        ),
    ]
    used = sum(layer.token_used for layer in layers)
    return CompressedContextPack(
        id=f"context-{act.id}",
        token_budget=budget,
        token_used=used,
        layers=layers,
        query=query or act.summary[:120],
        notes="act_scoped_v1",
    )


def pack_as_prompt_block(pack: CompressedContextPack) -> str:
    """Flatten pack for LLM system/user injection."""
    parts: list[str] = []
    for layer in pack.layers:
        if not layer.content:
            continue
        parts.append(f"### {layer.name.upper()}\n{layer.content}")
    return "\n\n".join(parts)


def context_dict_for_extras(pack: CompressedContextPack) -> dict[str, Any]:
    return pack.model_dump(mode="json")
