"""
StorybookPageAgent — topic → page plan with style lock + shot variety.

Why: critique fails when pages drift in style/character and share one weak zoom.
"""

from __future__ import annotations

import re
from typing import Any

from agents.narrative_beat_agent import plan_silent_beats
from libraries.silent_beats import CameraHint
from libraries.storybook_contract import (
    CameraMove,
    ShotSize,
    StorybookPage,
    StorybookPlan,
)
from libraries.storybook_prompt_craft import craft_page_still_prompt
from libraries.storybook_visual_directing import direct_scene

DEFAULT_STYLE_LOCK = (
    "STYLE LOCK: richly colored children's storybook painting directed like cinema — "
    "emotion readable at first glance, strong focal hook, hand-painted gouache and soft "
    "watercolor washes with visible brush texture, vivid saturated colors "
    "(teal forest, warm orange fox, cool cyan-blue lantern glow, soft yellow firefly "
    "sparks), cohesive painterly look on every page, full-bleed 16:9 edge-to-edge "
    "(absolutely no picture frame, no oval mat, no beige border card, no comic gutters, "
    "no stage proscenium, no letterbox bars, not a whiteboard sketch, not pen outline only, "
    "not a flat postcard composition)"
)


def _character_bible(topic: str, title: str) -> str:
    """Stable hero description for every page (first noun-ish hero from topic)."""
    low = (topic or "").lower()
    if "fox" in low or "روباه" in topic:
        hero = (
            "one small orange fox with white chest and white-tipped tail, "
            "simple cute face, consistent proportions"
        )
        props = (
            "PROP LOCK: glowing BLUE glass lantern only (never orange/yellow lantern body); "
            "fireflies are tiny soft yellow light dots/sparks only (never bees, wings, or insects)"
        )
    else:
        hero = f"one consistent lead character for '{title}', same design every page"
        props = "PROP LOCK: keep key props identical in color and silhouette on every page"
    return (
        f"CHARACTER BIBLE: exactly ONE {hero}; never two foxes, never a twin, "
        f"never duplicate the hero twice in one frame; "
        f"keep costume/colors identical across pages. {props}"
    )


def _camera_for_page(i: int, action: str, shot: ShotSize) -> CameraMove:
    """Ken Burns move after the still is directed (angle lives in the still)."""
    low = action.lower()
    if re.search(r"\b(left|چپ)\b", low):
        return "slow_pan_left"
    if re.search(r"\b(right|راست)\b", low):
        return "slow_pan_right"
    if shot == "close":
        return "subtle_zoom_in"
    if shot == "medium":
        return "slow_pan_right" if i % 2 == 0 else "slow_pan_left"
    return "subtle_zoom_in" if i % 2 == 0 else "static"


def plan_storybook(
    topic: str,
    *,
    title: str = "Story",
    language: str = "en",
    target_sec: float = 36.0,
    max_pages: int = 12,
    crossfade_sec: float = 0.9,
) -> StorybookPlan:
    """
    Deterministic storybook pages: concept directing first, then paint locks.
    """
    beats = plan_silent_beats(
        topic,
        target_sec=float(target_sec),
        language=language,
        max_beats=max_pages,
    )
    moods = {b.mood for b in beats}
    ambiance = "soft cinematic dusk light, calm colorful storybook painting"
    if "tense" in moods:
        ambiance = "moody soft dusk, quiet tension, colorful storybook painting"
    elif "warm" in moods:
        ambiance = "warm soft dusk glow, gentle colorful storybook painting"

    style_lock = DEFAULT_STYLE_LOCK
    character_bible = _character_bible(topic, title)
    sheet_prompt = (
        f"Character model sheet for storybook '{title}': {character_bible}. "
        f"{style_lock}. Neutral pose on a simple dusk painted forest path, "
        f"full-bleed 16:9, no text, no frame, no border."
    )

    pages: list[StorybookPage] = []
    n_beats = len(beats)
    for b in beats:
        direction = direct_scene(
            b.visual_action,
            mood=b.mood,
            page_index=b.index,
            page_count=n_beats,
        )
        shot = direction.shot
        cam_hint: CameraHint = b.camera_hint
        if cam_hint in ("slow_pan_left", "slow_pan_right"):
            camera: CameraMove = cam_hint  # type: ignore[assignment]
        else:
            camera = _camera_for_page(b.index, b.visual_action, shot)
        pages.append(
            StorybookPage(
                index=b.index,
                visual_action=b.visual_action,
                hold_sec=float(b.hold_sec),
                camera=camera,
                shot=shot,
                mood=b.mood,
                concept=direction.concept,
                emotion=direction.emotion,
                camera_angle=direction.camera_angle,
                staging=direction.staging,
                visual_hook=direction.visual_hook,
                still_prompt=craft_page_still_prompt(
                    title=title,
                    action=b.visual_action,
                    ambiance=ambiance,
                    topic=topic,
                    style_lock=style_lock,
                    character_bible=character_bible,
                    shot=shot,
                    page_index=b.index,
                    page_count=n_beats,
                    direction=direction,
                ),
            )
        )
    return StorybookPlan(
        title=title,
        topic=topic,
        language=language,
        target_sec=float(target_sec),
        crossfade_sec=float(crossfade_sec),
        pages=pages,
        global_ambiance=ambiance,
        style_lock=style_lock,
        character_bible=character_bible,
        character_sheet_prompt=sheet_prompt,
    )


def run_storybook_page_agent(
    topic: str,
    *,
    title: str = "Story",
    language: str = "en",
    target_sec: float = 36.0,
) -> dict[str, Any]:
    """AgentBus-style entry."""
    plan = plan_storybook(
        topic, title=title, language=language, target_sec=target_sec
    )
    return {
        "agent": "StorybookPageAgent",
        "version": "3-concept-directing",
        "plan": plan.model_dump(mode="json"),
    }
