"""
Concept → cinematic still direction for storybook pages.

Why: first-glance meaning beats pretty-but-flat postcards; each beat must
encode emotion, angle, staging, and a visual hook before paint details.
"""

from __future__ import annotations

from dataclasses import dataclass

from libraries.storybook_contract import CameraAngle, ShotSize


@dataclass(frozen=True)
class SceneDirection:
    """Directing card that makes a silent beat readable in one look."""

    concept: str
    emotion: str
    camera_angle: CameraAngle
    shot: ShotSize
    staging: str
    lighting: str
    visual_hook: str
    face_read: str


def direct_scene(
    action: str,
    *,
    mood: str = "calm",
    page_index: int = 0,
    page_count: int = 1,
) -> SceneDirection:
    """
    Map beat text + mood into a first-glance directing package.

    Priority: emotion readability over decorative clutter.
    """
    low = (action or "").lower()
    fa = action or ""
    mood_l = (mood or "calm").lower()
    progress = f"{page_index + 1}/{max(1, page_count)}"

    # Specific story beats before generic lantern/mood fallbacks.
    camera_angle: CameraAngle
    shot: ShotSize
    if any(w in low for w in ("hill", "star", "moon", "تپه", "ستار", "ماه")):
        emotion = "hope"
        concept = "arrival: light held high against the open night"
        camera_angle = "low_angle"
        shot = "wide"
        staging = (
            "hero on hilltop crest, lantern raised; vast star field above; "
            "hero silhouette strong against sky (single figure only)"
        )
        lighting = (
            "lantern cyan pool at feet + cool moon rim; stars as soft glitter; "
            "no second moon, no twin hero"
        )
        visual_hook = (
            "FIRST GLANCE HOOK: triumphant low-angle hero under one crescent moon, "
            "lantern lifted like a signal to the sky"
        )
        face_read = "upturned face, quiet pride, eyes bright"
    elif any(w in low for w in ("bridge", "cross", "walk", "پل", "عبور")):
        emotion = "resolve"
        concept = "threshold: crossing means committing to the journey"
        camera_angle = "eye_level"
        shot = "medium"
        staging = (
            "bridge diagonal from lower-left to mid-right; hero mid-crossing with lantern; "
            "destination implied beyond the far bank"
        )
        lighting = (
            "lantern leads the way onto bridge planks; cool water reflection; "
            "slight warmer light on the far side (hope)"
        )
        visual_hook = (
            "FIRST GLANCE HOOK: diagonal bridge + moving hero + lantern trail of light "
            "pulling the eye across the gap"
        )
        face_read = "focused forward gaze, ears alert, confident stride"
    elif any(w in low for w in ("mist", "fog", "alone", "tiny", "مه", "تنها")):
        emotion = "unease" if "tense" in mood_l else "loneliness"
        concept = "scale: the world is vast; the hero is small but moving"
        camera_angle = "high_angle"
        shot = "wide"
        staging = (
            "hero very small in lower third of a wide path/river mist; negative space above; "
            "path leads the eye deeper into haze"
        )
        lighting = (
            "diffused cool mist light; lantern is a small but sharp cyan beacon; "
            "low contrast except the beacon"
        )
        visual_hook = (
            "FIRST GLANCE HOOK: a tiny warm fox silhouette under a huge soft mist, "
            "anchored by one cold blue spark of lantern"
        )
        face_read = "face optional/small; body language huddled-forward, determined"
    elif any(w in low for w in ("firefl", "spark", "کرم", "gather")):
        emotion = "wonder"
        concept = "companionship: tiny lights answer the lantern"
        camera_angle = "eye_level"
        shot = "close"
        staging = (
            "tight on hero face and lantern; firefly sparks arc around the head/shoulders "
            "like a living halo; background softly melted"
        )
        lighting = (
            "lantern cyan fill on face + speckles of warm yellow firefly accents; "
            "shallow depth so emotion stays sharp"
        )
        visual_hook = (
            "FIRST GLANCE HOOK: constellation of yellow sparks circling the blue lantern "
            "and the hero's eyes catching both lights"
        )
        face_read = "gentle smile, eyes reflecting blue+gold points of light"
    elif any(w in low for w in ("find", "discover", "پیدا", "کشف")) or (
        "lantern" in low or "فانوس" in fa
    ):
        emotion = "awe"
        concept = "discovery: a secret light changes the night"
        camera_angle = "low_angle"
        shot = "medium"
        staging = (
            "hero in lower-left third looking up/toward the glowing blue lantern; "
            "lantern placed on upper-right power point; clear eye-line to the light"
        )
        lighting = (
            "cool cyan lantern as dominant key; warm dusk rim on hero fur; "
            "surrounding forest falls into softer teal shadow"
        )
        visual_hook = (
            "FIRST GLANCE HOOK: one brilliant blue lantern bloom against deep teal woods — "
            "impossible to miss in the first 200ms"
        )
        face_read = "soft open eyes, quiet wonder, mouth relaxed (not cartoon scream)"
    elif "tense" in mood_l:
        emotion = "tension"
        concept = "pressure: something unseen presses on the moment"
        camera_angle = "over_shoulder"
        shot = "medium"
        staging = "hero off-center; darker mass on the opposite third; shallow escape path"
        lighting = "harder contrast, cooler fill, lantern as only safe warm/cool anchor"
        visual_hook = (
            "FIRST GLANCE HOOK: unbalanced frame with one bright safe light and a dark void"
        )
        face_read = "tense eyes, body coiled"
    elif "warm" in mood_l:
        emotion = "warmth"
        concept = "comfort: the world feels kind for a breath"
        camera_angle = "eye_level"
        shot = "medium"
        staging = "hero centered-soft with breathing room; friendly environment wraps them"
        lighting = "warm dusk wrap + gentle lantern accent"
        visual_hook = (
            "FIRST GLANCE HOOK: cozy color bloom and a clear, friendly hero pose"
        )
        face_read = "soft smile, relaxed brows"
    else:
        emotion = "calm"
        concept = "breath: a clear story beat the eye can rest on"
        camera_angle = "eye_level"
        shot = "medium"
        staging = "hero readable in midground; simple depth layers; uncluttered focal point"
        lighting = "balanced dusk fill with a single accent light"
        visual_hook = (
            "FIRST GLANCE HOOK: one clean focal hero/prop with vivid storybook color"
        )
        face_read = "neutral-soft expression, clear silhouette"

    # Opening page bias: captivate harder.
    if page_index == 0 and emotion in {"calm", "warmth"}:
        emotion = "awe"
        visual_hook = (
            "FIRST GLANCE HOOK: cinematic opening tableau — vivid hero color against "
            "atmospheric depth, one irresistible light accent"
        )

    _ = (fa, progress)
    return SceneDirection(
        concept=concept,
        emotion=emotion,
        camera_angle=camera_angle,
        shot=shot,
        staging=staging,
        lighting=lighting,
        visual_hook=visual_hook,
        face_read=face_read,
    )


def format_directing_block(d: SceneDirection) -> str:
    """Serialize directing card into prompt layers image models obey."""
    return (
        f"CONCEPT: {d.concept}\n"
        f"EMOTION TO READ AT FIRST GLANCE: {d.emotion}\n"
        f"{d.visual_hook}\n"
        f"CAMERA ANGLE: {d.camera_angle.replace('_', ' ')}\n"
        f"STAGING: {d.staging}\n"
        f"LIGHTING INTENT: {d.lighting}\n"
        f"FACE/BODY READ: {d.face_read}\n"
        "PRIORITY: emotion and concept must be obvious before fine details; "
        "make the frame magnetic, not a flat postcard."
    )
