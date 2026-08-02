"""
StorybookPromptDirector — enrich page still prompts from the full story.

Why: deterministic craft is safe for CI; live Gemini text can add cinematic
scene detail per beat while we re-graft style/character locks.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from libraries.storybook_contract import StorybookPlan, StorybookPage
from libraries.storybook_prompt_craft import looks_like_rich_prompt

TextFn = Callable[[str], str]


def _director_system_prompt(plan: StorybookPlan) -> str:
    pages_brief = "\n".join(
        f"- index={p.index} emotion={p.emotion} angle={p.camera_angle} "
        f"shot={p.shot} concept={p.concept} beat={p.visual_action} hook={p.visual_hook}"
        for p in plan.pages
    )
    return f"""You are a silent storybook art director writing IMAGE prompts.
Priority: the CONCEPT and EMOTION must be obvious at first glance (magnetic frame).
Story title: {plan.title}
Full story/topic: {plan.topic}
Global ambiance: {plan.global_ambiance}

You MUST keep these locks VERBATIM inside every still_prompt:
1) {plan.style_lock}
2) {plan.character_bible}

For EACH page write a detailed English still_prompt with ALL of these sections:
- STYLE LOCK + CHARACTER BIBLE (verbatim)
- CONCEPT + EMOTION TO READ AT FIRST GLANCE + VISUAL HOOK / FIRST GLANCE HOOK
- CAMERA ANGLE + STAGING (compose for meaning, not flat postcard)
- PAGE BEAT (what happens now)
- SHOT DIR (match the given shot: wide/medium/close)
- SCENE SPEC with foreground / midground / background / lighting / time of day
- NEGATIVE (no text, no picture frame, no oval mat, no open-book crease, no twin hero)

Pages (honor the given emotion/angle/hook; enrich paint detail only):
{pages_brief}

Return ONLY JSON (no markdown fences):
{{
  "pages": [
    {{"index": 0, "still_prompt": "..."}}
  ]
}}
Rules:
- One object per page index 0..{len(plan.pages) - 1}
- Prompts must differ by beat (do not clone the same scene)
- Keep prop colors locked (e.g. blue lantern if mentioned in the bible)
- Full-bleed 16:9 only
- Emotion readable in under one second of looking
"""


def parse_director_prompts(raw: str, plan: StorybookPlan) -> dict[int, str]:
    """Parse director JSON and graft missing locks onto each prompt."""
    cleaned = (raw or "").strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        data = json.loads(cleaned[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("director JSON must be an object")
    pages = data.get("pages")
    if not isinstance(pages, list):
        raise ValueError("director JSON missing pages[]")

    out: dict[int, str] = {}
    for item in pages:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        prompt = str(item.get("still_prompt") or "").strip()
        if not prompt:
            continue
        if plan.style_lock not in prompt:
            prompt = f"{plan.style_lock}\n{prompt}"
        if plan.character_bible not in prompt:
            prompt = f"{plan.character_bible}\n{prompt}"
        if "negative" not in prompt.lower() and "no text" not in prompt.lower():
            prompt = (
                prompt
                + "\nNEGATIVE: no text, no picture frame, no oval mat, "
                "no open-book crease, no twin hero"
            )
        # Re-graft concept directing if the LLM dropped it.
        page = next((p for p in plan.pages if p.index == idx), None)
        if page is not None:
            if "concept" not in prompt.lower():
                prompt = f"CONCEPT: {page.concept}\n{prompt}"
            if "first glance" not in prompt.lower() and "visual hook" not in prompt.lower():
                prompt = f"{page.visual_hook}\n{prompt}"
            if "emotion" not in prompt.lower():
                prompt = f"EMOTION TO READ AT FIRST GLANCE: {page.emotion}\n{prompt}"
        out[idx] = prompt
    if not out:
        raise ValueError("director returned no usable page prompts")
    return out


def enrich_plan_prompts(
    plan: StorybookPlan,
    *,
    text_fn: TextFn | None = None,
    timeout: float = 90.0,
) -> StorybookPlan:
    """
    Replace page still_prompt strings via LLM; fail-soft to original craft.

    Inject ``text_fn`` in tests. Live path uses Gemini ``generate_text``.
    """
    if text_fn is None:
        from libraries.gemini_client import generate_text

        def text_fn(prompt: str) -> str:  # type: ignore[no-redef]
            return generate_text(
                prompt,
                timeout=timeout,
                max_output_tokens=8192,
                temperature=0.35,
            )

    try:
        raw = text_fn(_director_system_prompt(plan))
        mapping = parse_director_prompts(raw, plan)
    except Exception:  # noqa: BLE001
        return plan

    new_pages: list[StorybookPage] = []
    for p in plan.pages:
        prompt = mapping.get(p.index, p.still_prompt)
        if not looks_like_rich_prompt(prompt):
            # Keep crafted original if director output is too thin
            prompt = p.still_prompt
        new_pages.append(p.model_copy(update={"still_prompt": prompt}))
    return plan.model_copy(update={"pages": new_pages})


def run_storybook_prompt_director(
    plan: StorybookPlan,
    *,
    live: bool = False,
) -> dict[str, Any]:
    """Agent-style entry for reports."""
    if not live:
        return {
            "agent": "StorybookPromptDirector",
            "version": "1",
            "mode": "craft_only",
            "plan": plan.model_dump(mode="json"),
        }
    enriched = enrich_plan_prompts(plan)
    return {
        "agent": "StorybookPromptDirector",
        "version": "1",
        "mode": "llm_enrich",
        "plan": enriched.model_dump(mode="json"),
    }
