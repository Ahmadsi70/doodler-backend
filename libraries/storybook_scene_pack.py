"""
Fixed multi-scene story packs with locked continuity.

Why: authored kids stories need exact 7-beat cards; free topic splitting
cannot guarantee the written sequence and prop continuity.
"""

from __future__ import annotations

from dataclasses import dataclass

from libraries.storybook_contract import (
    CameraAngle,
    CameraMove,
    ShotSize,
    StorybookPage,
    StorybookPlan,
)
from libraries.storybook_prompt_craft import craft_page_still_prompt
from libraries.storybook_visual_directing import SceneDirection, format_directing_block


@dataclass(frozen=True)
class SceneCard:
    """One authored storyboard frame."""

    visual_action: str
    detail: str
    emotion: str
    concept: str
    camera_angle: CameraAngle
    shot: ShotSize
    staging: str
    lighting: str
    visual_hook: str
    face_read: str
    mood: str = "warm"
    camera: CameraMove = "subtle_zoom_in"
    narration: str = ""
    # Offline/SAPI path when Persian neural TTS is unreachable.
    narration_en: str = ""


@dataclass(frozen=True)
class StoryPack:
    """Complete continuity-locked story pack."""

    title: str
    topic: str
    language: str
    style_lock: str
    character_bible: str
    scenes: tuple[SceneCard, ...]


KIDS_WATERCOLOR_STYLE = (
    "STYLE LOCK: cheerful digital watercolor for children ages 5-9, soft rounded "
    "shapes, gentle outlines, bright happy saturated colors, soft wet-on-wet washes, "
    "cozy storybook charm, emotion readable at first glance, full-bleed 16:9 "
    "edge-to-edge (no picture frame, no oval mat, no beige border card, no comic "
    "gutters, no stage proscenium, no letterbox bars, not photoreal, not scary, "
    "absolutely no written words, no letters, no Persian or English text anywhere in "
    "the image, no signs, no labels, no captions)"
)

ARVIN_BIBLE = (
    "CHARACTER BIBLE: exactly ONE boy named Arvin, about 7 years old, "
    "ALWAYS wearing big round glasses (never without glasses), curious friendly face, "
    "short brown hair, yellow T-shirt and blue shorts — identical design every page; "
    "never a second boy, never a twin, never a glasses-less duplicate. "
    "PROP LOCK: one old wooden crate/box with rusty gears (same box every page); "
    "small colorful balloons when present (same balloon colors); later one cute fat "
    "silkworm with a tiny sewing hat; mint-leaf chocolate tree; leaf-fabric parachute; "
    "mother only in the final scene, warm smile, consistent with family home."
)


ARVIN_LAST_INVENTION = StoryPack(
    title="آخرین اختراع نابغه‌ی کوچک",
    topic=(
        "Arvin, a little genius with round glasses, invents a flying wooden gear box "
        "with balloons, floats through clouds, lands in a chocolate mint tree, "
        "befriends a silkworm, and returns home by leaf parachute at sunset."
    ),
    language="fa",
    style_lock=KIDS_WATERCOLOR_STYLE,
    character_bible=ARVIN_BIBLE,
    scenes=(
        SceneCard(
            visual_action=(
                "Messy bedroom full of scribbled papers; Arvin sits on the floor staring "
                "at an old wooden gear box as sunbeams light floating dust."
            ),
            detail=(
                "Messy child's bedroom with scribbled papers everywhere; Arvin with big "
                "round glasses sits on the floor gazing at an old wooden box with rusty "
                "gears; warm sunlight from the window; dust motes in the air."
            ),
            emotion="curiosity",
            concept="mystery: a forgotten box invites discovery",
            camera_angle="eye_level",
            shot="medium",
            staging=(
                "Arvin lower-left on the floor; wooden gear box as bright focal point "
                "center-right; sunbeam diagonal leading eye to the box"
            ),
            lighting="warm sunbeam key through window; soft room fill; dust sparkles",
            visual_hook=(
                "FIRST GLANCE HOOK: glowing dust in a sunbeam hitting a mysterious "
                "wooden gear box while a bespectacled boy leans in"
            ),
            face_read="wide curious eyes behind round glasses, mouth slightly open",
            mood="warm",
            camera="subtle_zoom_in",
        ),
        SceneCard(
            visual_action=(
                "Close on Arvin's workbench as he ties colorful balloons to the wooden "
                "box; desk lamp casts shadow; orange soda spilled on the floor."
            ),
            detail=(
                "Close workbench: Arvin attaches small colorful balloons to the wooden "
                "gear box; large desk lamp shadows his face; hammer and screwdriver "
                "nearby; orange drink bottle spilled, orange puddle on floor."
            ),
            emotion="excitement",
            concept="making: noisy impatient invention energy",
            camera_angle="eye_level",
            shot="close",
            staging=(
                "hands + balloons + box fill the frame; lamp upper corner; orange spill "
                "as playful foreground accent"
            ),
            lighting="hard desk-lamp key creating inventive face shadow; vivid balloon colors",
            visual_hook=(
                "FIRST GLANCE HOOK: rainbow balloons being tied to a rusty gear box "
                "under a dramatic lamp — pure kid-inventor chaos"
            ),
            face_read="excited impatient grin, glasses reflecting lamp light",
            mood="warm",
            camera="subtle_zoom_in",
        ),
        SceneCard(
            visual_action=(
                "Wide yard shot: balloon wooden box lifts off; Arvin hangs surprised with "
                "feet dangling; small birds fly past; box shadow on grass."
            ),
            detail=(
                "Wide backyard: wooden box with colorful balloons rising; Arvin looking "
                "down in surprise, feet dangling in air; tiny birds passing astonished; "
                "box shadow on green grass."
            ),
            emotion="awe",
            concept="liftoff: surprise freedom of first flight",
            camera_angle="low_angle",
            shot="wide",
            staging=(
                "flying box+Arvin upper third against sky; yard and shadow below; birds "
                "as motion accents on the side"
            ),
            lighting="bright cheerful daylight; crisp shadow of box on lawn",
            visual_hook=(
                "FIRST GLANCE HOOK: boy and balloon-box floating above the yard with "
                "dangling feet and a clear ground shadow"
            ),
            face_read="shocked open mouth, thrilled eyes",
            mood="hopeful",
            camera="subtle_zoom_in",
        ),
        SceneCard(
            visual_action=(
                "Arvin among cream-pink clouds unties balloon knots hooked to a big cloud; "
                "sparkly rain below forms a tiny rainbow."
            ),
            detail=(
                "Arvin sitting in soft cream and pink clouds; balloons hooked to a large "
                "cloud; he unties knots; glittery gentle rain falls below making a small "
                "rainbow."
            ),
            emotion="wonder",
            concept="dreamflight: calm adventure above the world",
            camera_angle="eye_level",
            shot="medium",
            staging=(
                "Arvin centered in fluffy cloud nest; rainbow lower frame; balloons as "
                "color accents around him"
            ),
            lighting="soft pastel cloud light; rainbow glow from below",
            visual_hook=(
                "FIRST GLANCE HOOK: pastel cloud throne + tiny rainbow under sparkly rain "
                "with colorful balloons"
            ),
            face_read="peaceful adventurous smile, focused on untying knots",
            mood="calm",
            camera="slow_pan_right",
        ),
        SceneCard(
            visual_action=(
                "Wooden box stuck in a mint-leaf chocolate-fruit tree; Arvin hangs upside "
                "down biting a chocolate fruit; round-eyed squirrel stares."
            ),
            detail=(
                "Odd tree with mint-green leaves and round brown chocolate fruits; wooden "
                "box snagged in branches; Arvin hanging upside down biting a chocolate "
                "fruit; a squirrel with round eyes stares from above."
            ),
            emotion="joy",
            concept="comic landing: funny discovery in a candy tree",
            camera_angle="eye_level",
            shot="medium",
            staging=(
                "upside-down Arvin as center gag; squirrel top-right reacting; chocolate "
                "fruit in hand as prop read"
            ),
            lighting="dappled leafy daylight; warm chocolate browns vs cool mint greens",
            visual_hook=(
                "FIRST GLANCE HOOK: upside-down bespectacled boy eating chocolate fruit "
                "in a mint tree while a shocked squirrel stares"
            ),
            face_read="upside-down silly happy chew, glasses still on",
            mood="warm",
            camera="subtle_zoom_in",
        ),
        SceneCard(
            visual_action=(
                "Close: Arvin shakes hands with a cute big silkworm in a tiny sewing hat; "
                "silkworm holds a leaf umbrella; wooden box behind on the branch."
            ),
            detail=(
                "Close friendship beat: Arvin and a cute large silkworm wearing a tiny "
                "sewing hat; silkworm holds a big leaf like an umbrella over Arvin; they "
                "shake hands happily; wooden box rests on the branch behind them."
            ),
            emotion="warmth",
            concept="friendship: kindness under a leaf umbrella",
            camera_angle="eye_level",
            shot="close",
            staging=(
                "two faces filling frame; leaf umbrella canopy above; box softly behind "
                "for continuity"
            ),
            lighting="warm friendly fill under leaf shade; soft rim light",
            visual_hook=(
                "FIRST GLANCE HOOK: handshake between boy-with-glasses and hatted "
                "silkworm under a leaf umbrella"
            ),
            face_read="big warm smile; silkworm equally cute and kind",
            mood="warm",
            camera="subtle_zoom_in",
        ),
        SceneCard(
            visual_action=(
                "Wide rooftop landing at orange-purple sunset: Arvin waves from wooden box "
                "with leaf-fabric parachute; mother smiles from lower window."
            ),
            detail=(
                "Distant view of Arvin's house rooftop; wooden box gently lands with a "
                "large leaf-fabric parachute; tired but happy Arvin waves; mother smiles "
                "from a lower-floor window; sunset sky orange and purple."
            ),
            emotion="belonging",
            concept="homecoming: safe return and family warmth",
            camera_angle="high_angle",
            shot="wide",
            staging=(
                "rooftop landing center; parachute dome as silhouette against sunset; "
                "mother in glowing lower window as emotional anchor"
            ),
            lighting="orange-purple sunset wash; warm window glow; soft parachute shadow",
            visual_hook=(
                "FIRST GLANCE HOOK: leaf parachute landing on a rooftop at glowing sunset "
                "while mother waves from the window"
            ),
            face_read="tired happy wave; mother gentle smile",
            mood="warm",
            camera="static",
        ),
    ),
)


def plan_from_scene_pack(
    pack: StoryPack,
    *,
    target_sec: float | None = None,
    crossfade_sec: float = 0.7,
) -> StorybookPlan:
    """
    Build a StorybookPlan from authored scene cards (exact count + continuity).
    """
    n = len(pack.scenes)
    if n < 1:
        raise ValueError("story pack needs at least one scene")
    total = float(target_sec) if target_sec is not None else float(n * 7.0)
    hold = max(2.5, total / float(n))
    sheet = (
        f"Character model sheet for '{pack.title}': {pack.character_bible}. "
        f"{pack.style_lock}. Neutral standing pose of the lead character with key props "
        f"beside them, full-bleed 16:9, no text, no frame."
    )
    pages: list[StorybookPage] = []
    for i, card in enumerate(pack.scenes):
        direction = SceneDirection(
            concept=card.concept,
            emotion=card.emotion,
            camera_angle=card.camera_angle,
            shot=card.shot,
            staging=card.staging,
            lighting=card.lighting,
            visual_hook=card.visual_hook,
            face_read=card.face_read,
        )
        # Embed exact authored detail into the beat line for the image model.
        action = f"{card.visual_action} DETAIL: {card.detail}"
        prompt = craft_page_still_prompt(
            title=pack.title,
            action=action,
            ambiance="cheerful kids watercolor adventure",
            topic=pack.topic,
            style_lock=pack.style_lock,
            character_bible=pack.character_bible,
            shot=card.shot,
            page_index=i,
            page_count=n,
            direction=direction,
        )
        # Reinforce pack-specific detail + directing block already included.
        if card.detail not in prompt:
            prompt = f"{prompt}\nAUTH SCENE DETAIL: {card.detail}"
        if format_directing_block(direction).split("\n", 1)[0] not in prompt:
            prompt = f"{format_directing_block(direction)}\n{prompt}"
        pages.append(
            StorybookPage(
                index=i,
                visual_action=card.visual_action,
                hold_sec=round(hold, 3),
                camera=card.camera,
                shot=card.shot,
                mood=card.mood,
                concept=card.concept,
                emotion=card.emotion,
                camera_angle=card.camera_angle,
                staging=card.staging,
                visual_hook=card.visual_hook,
                narration=card.narration,
                narration_en=card.narration_en,
                still_prompt=prompt,
            )
        )
    return StorybookPlan(
        title=pack.title,
        topic=pack.topic,
        language=pack.language,
        target_sec=round(hold * n, 3),
        crossfade_sec=float(crossfade_sec),
        pages=pages,
        global_ambiance="cheerful kids watercolor adventure",
        style_lock=pack.style_lock,
        character_bible=pack.character_bible,
        character_sheet_prompt=sheet,
    )


# Educational layered sample: Story visuals + narration (explainer audio layer)
_EDU_BIBLE = (
    "CHARACTER BIBLE: exactly ONE friendly water drop character named Dropi, "
    "round shiny blue body, small cute eyes, consistent every page; "
    "PROP LOCK: yellow sun, white fluffy clouds, green hills, blue lake — "
    "same shapes/colors across scenes; no text letters in the image."
)

WATER_CYCLE_KIDS = StoryPack(
    title="Dropi's Water Journey",
    topic=(
        "Kids educational watercolor story: Dropi the water drop travels through "
        "the water cycle — lake, vapor, cloud, rain, and return home."
    ),
    language="en",
    style_lock=KIDS_WATERCOLOR_STYLE,
    character_bible=_EDU_BIBLE,
    scenes=(
        SceneCard(
            visual_action="Dropi floats happily on a bright blue lake under a warm sun.",
            detail=(
                "Wide cheerful lake scene; Dropi the cute blue water-drop character "
                "bobbing on sparkling water; yellow sun upper-right; green hills behind."
            ),
            emotion="warmth",
            concept="home water: liquid water waits in the lake",
            camera_angle="eye_level",
            shot="wide",
            staging="Dropi lower-center on lake; sun power-point upper right; open sky",
            lighting="warm sunny key; cool blue water fill",
            visual_hook="FIRST GLANCE HOOK: shiny blue drop on a bright lake under a big sun",
            face_read="happy calm smile",
            mood="warm",
            camera="subtle_zoom_in",
            narration="Water rests calmly in the lake. Here is our little drop.",
            narration_en="Water rests calmly in the lake. Here is our little drop.",
        ),
        SceneCard(
            visual_action="Sun warms Dropi; Dropi rises upward as soft sparkly vapor.",
            detail=(
                "Medium shot: yellow sun beams hit Dropi; Dropi stretches upward into "
                "soft sparkly vapor trails rising to the sky."
            ),
            emotion="awe",
            concept="evaporation: heat turns water into vapor",
            camera_angle="low_angle",
            shot="medium",
            staging="sun upper frame; Dropi mid rising with vapor ribbons",
            lighting="strong warm sunbeams; cool vapor accents",
            visual_hook="FIRST GLANCE HOOK: sunbeams lifting a blue drop into sparkling vapor",
            face_read="surprised delighted eyes looking up",
            mood="warm",
            camera="subtle_zoom_in",
            narration="The warm sun lifts the drop upward. Water becomes vapor.",
            narration_en="The warm sun lifts the drop upward. Water becomes vapor.",
        ),
        SceneCard(
            visual_action="Many vapor friends gather into a soft white cloud around Dropi.",
            detail=(
                "Close-medium: fluffy cream-white cloud forming; Dropi and tiny vapor "
                "friends clustering inside the cloud."
            ),
            emotion="wonder",
            concept="condensation: vapor gathers into a cloud",
            camera_angle="eye_level",
            shot="close",
            staging="Dropi centered in soft cloud puff; sky soft blue around",
            lighting="soft diffused cloud light; gentle rim",
            visual_hook="FIRST GLANCE HOOK: cute drop nestled inside a growing fluffy cloud",
            face_read="cozy wonder smile",
            mood="calm",
            camera="slow_pan_right",
            narration="Vapor friends gather together and build a soft cloud.",
            narration_en="Vapor friends gather together and build a soft cloud.",
        ),
        SceneCard(
            visual_action="Heavy cloud rains; Dropi falls as a happy raindrop toward green land.",
            detail=(
                "Wide rainy sky: cloud releases glittery rain; Dropi falling as a clear "
                "raindrop toward green fields below."
            ),
            emotion="joy",
            concept="precipitation: water falls back as rain",
            camera_angle="high_angle",
            shot="wide",
            staging="cloud top; rain streaks diagonal; Dropi mid-fall; land below",
            lighting="cool rain light with a warm rainbow hint",
            visual_hook="FIRST GLANCE HOOK: rain streaks and one clear Dropi falling homeward",
            face_read="excited joyful fall pose",
            mood="hopeful",
            camera="subtle_zoom_in",
            narration="The heavy cloud rains. The drop falls back toward the land.",
            narration_en="The heavy cloud rains. The drop falls back toward the land.",
        ),
        SceneCard(
            visual_action="Dropi rejoins the lake among friends under a soft sunset.",
            detail=(
                "Wide sunset lake return: Dropi splashes back into blue lake with other "
                "drop friends; orange-purple sky; warm calm ending."
            ),
            emotion="belonging",
            concept="return: the water cycle begins again",
            camera_angle="eye_level",
            shot="wide",
            staging="lake center; Dropi splash foreground; sunset sky backdrop",
            lighting="warm sunset wash; cool lake reflection",
            visual_hook="FIRST GLANCE HOOK: splash-home reunion on a glowing sunset lake",
            face_read="tired happy smile",
            mood="warm",
            camera="static",
            narration="The drops return to the lake, and the water journey begins again.",
            narration_en="The drops return to the lake, and the water journey begins again.",
        )
    ),
)
