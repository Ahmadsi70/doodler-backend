"""
Deterministic story-aware still prompts for storybook pages.

Why: mock/CI need rich, beat-specific prompts without an LLM; live can enrich
on top while keeping the same lock layers.
"""

from __future__ import annotations

from libraries.storybook_contract import ShotSize
from libraries.storybook_visual_directing import SceneDirection, format_directing_block

_NEGATIVE = (
    "NEGATIVE: no text, no letters, no watermark, no subtitles, no speech bubbles, "
    "no logos, no picture frame, no oval mat, no beige border card, no comic gutters, "
    "no open-book center crease, no stage proscenium, no letterbox bars, "
    "no second copy of the hero, no twin hero, no duplicate lead character, "
    "no flat centered postcard pose, no emotionless stare"
)


def _time_of_day(action: str, topic: str) -> str:
    blob = f"{action} {topic}".lower()
    if any(w in blob for w in ("star", "night", "moon", "شب", "ستار")):
        return "deep night with crescent moon and soft starlight"
    if any(w in blob for w in ("dusk", "sunset", "twilight", "غروب", "شفق")):
        return "dusk / twilight with warm horizon and cool teal forest"
    if any(w in blob for w in ("dawn", "sunrise", "صبح", "طلوع")):
        return "soft dawn light"
    return "late dusk transitioning toward night"


def _scene_spec(action: str, *, topic: str, page_index: int, page_count: int) -> str:
    """Expand a short beat into layered scene directions."""
    low = action.lower()
    tod = _time_of_day(action, topic)
    fg = "foreground: soft grass clumps and path stones with gentle drop shadows"
    mid = "midground: the story action happens here with clear silhouette read"
    bg = "background: layered pine forest ridges fading into atmospheric haze"
    light = "key light from the blue lantern glow plus soft ambient dusk fill"
    extras: list[str] = []

    if "lantern" in low or "فانوس" in action:
        mid = (
            "midground: the small orange fox discovers a glowing BLUE glass lantern "
            "(cool cyan light on nearby leaves); fox does not yet carry it unless stated"
        )
        light = "strong cool blue lantern key light, warm rim from dusk sky"
        extras.append("lantern hangs or rests near path, never an orange lantern body")
    if "firefl" in low or "کرم" in action:
        extras.append(
            "swarm of tiny soft yellow light-dot fireflies only (no bee bodies/wings)"
        )
        mid = (
            "midground: fox near the blue lantern while firefly dots gather in a gentle arc"
        )
    if "bridge" in low or "پل" in action:
        mid = (
            "midground: arched wooden footbridge over a layered blue stream; "
            "fox walking toward or onto the bridge carrying the blue lantern"
        )
        fg = "foreground: dirt path curve leading the eye to the bridge"
    if "mist" in low or "fog" in low or "مه" in action:
        extras.append(
            "soft painted mist ribbons rising from the river, translucent watercolor layers"
        )
        mid = "midground: river under/near bridge with rising mist; fox may be small in frame"
    if "hill" in low or "star" in low or "تپه" in action:
        tod = "clear night on a quiet hilltop under stars"
        mid = (
            "midground: fox on a rounded hilltop holding the blue lantern; "
            "stars and crescent moon above, no oval vignette"
        )
        bg = "background: distant forest silhouettes under a star-dusted sky"
        light = "lantern warm pool on grass + cool moon rim light"

    progress = f"story progress {page_index + 1}/{max(1, page_count)}"
    extra = ("; ".join(extras) + ". ") if extras else ""
    return (
        f"SCENE SPEC ({progress}): time={tod}. {fg}. {mid}. {bg}. "
        f"Lighting: {light}. {extra}"
        f"Depth cues via layered painted planes, soft atmospheric perspective, and brush shadows."
    )


def _shot_block(shot: ShotSize) -> str:
    return {
        "wide": (
            "SHOT DIR: establishing wide 16:9; show environment + hero; "
            "hero occupies roughly lower third, not a tight close-up"
        ),
        "medium": (
            "SHOT DIR: medium 16:9; hero and key prop readable; "
            "environment still visible around them"
        ),
        "close": (
            "SHOT DIR: close 16:9 on hero face and/or glowing blue lantern; "
            "still full-bleed, no circular crop"
        ),
    }[shot]


def craft_page_still_prompt(
    *,
    title: str,
    action: str,
    ambiance: str,
    topic: str,
    style_lock: str,
    character_bible: str,
    shot: ShotSize,
    page_index: int,
    page_count: int,
    direction: SceneDirection | None = None,
) -> str:
    """
    Assemble a still prompt: concept directing first, then beat paint details.

    Why: models follow early constraints; emotion/hook must precede decoration.
    """
    scene = _scene_spec(
        action, topic=topic, page_index=page_index, page_count=page_count
    )
    shot_dir = _shot_block(shot)
    beat = f"PAGE BEAT: {action.strip()}"
    directing = format_directing_block(direction) if direction is not None else ""
    parts = [
        style_lock,
        character_bible,
        f"TITLE: {title}. Ambiance: {ambiance}.",
        directing,
        beat,
        shot_dir,
        scene,
        "Match attached character/style reference when provided.",
        _NEGATIVE,
    ]
    return "\n".join(p for p in parts if p)


def looks_like_rich_prompt(text: str) -> bool:
    """Heuristic: crafted/director prompts must carry lock + scene structure."""
    t = (text or "").lower()
    return (
        "style lock" in t
        and "character bible" in t
        and ("scene spec" in t or "foreground" in t)
        and ("concept" in t or "visual hook" in t or "first glance" in t)
        and ("negative" in t or "no text" in t)
    )
