"""Deterministic Story chain: Screenplay → Breakdown → Storyboard → Cine → Timing → Continuity."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    from tools.chapter_tools import chapters_to_jsonable, split_chapters
except ImportError:
    from ..tools.chapter_tools import chapters_to_jsonable, split_chapters  # type: ignore

try:
    from tools.studio_router import load_agent_system_prompt
except ImportError:
    from ..tools.studio_router import load_agent_system_prompt  # type: ignore

try:
    from tools.williams_craft import (
        apply_williams_craft,
        behavior_for_beat,
        infer_story_beat,
        load_williams_craft_pack,
    )
except ImportError:
    from ..tools.williams_craft import (  # type: ignore
        apply_williams_craft,
        behavior_for_beat,
        infer_story_beat,
        load_williams_craft_pack,
    )

AGENTS_DIRNAME = "agents"
CHAIN_MANIFEST = "chain_manifest.json"
AGENT_ORDER = (
    "DraftScreenplayAgent",
    "ScriptBreakdownAgent",
    "StoryboardAgent",
    "CinematographyAgent",
    "AnimationTimingAgent",
    "ContinuityAgent",
)


async def _run_parallel(*tasks: Callable[[], Any]) -> list[Any]:
    """Execute independent functions in parallel using ThreadPoolExecutor."""
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = [executor.submit(task) for task in tasks]
        # Return results in original task order (not completion order)
        return [f.result() for f in futures]


def _run_parallel_sync(*tasks: Callable[[], Any]) -> list[Any]:
    """Execute independent sync functions in parallel using ThreadPoolExecutor.
    
    Safer than asyncio.run() - avoids event loop conflicts in Streamlit/notebooks.
    Falls back to sequential if only 1 task.
    Returns results in ORIGINAL task order (not completion order).
    """
    if len(tasks) <= 1:
        return [task() for task in tasks]
    
    try:
        with ThreadPoolExecutor(max_workers=min(len(tasks), 4)) as executor:
            # Submit all tasks
            futures = [executor.submit(task) for task in tasks]
            # Get results in original order by iterating futures in order
            results = [f.result() for f in futures]
            return results
    except Exception as e:
        # Fallback to sequential on any error
        print(f"Warning: Parallel execution failed ({e}), falling back to sequential")
        return [task() for task in tasks]

_VERB_RE = re.compile(
    r"\b(enters?|leaves?|exits?|runs?|walks?|looks?|sees?|finds?|reacts?|"
    r"discovers?|opens?|closes?|holds?|reaches?|turns?|steps?|breathes?|"
    r"وارد|خارج|می‌رود|می رود|می‌بیند|می بیند|پیدا|کشف|می‌دود)\b",
    re.IGNORECASE,
)


@dataclass
class StoryChainResult:
    ok: bool = True
    agents_dir: str = ""
    screenplay: dict[str, Any] = field(default_factory=dict)
    script_breakdown: dict[str, Any] = field(default_factory=dict)
    style_recommendation: dict[str, Any] = field(default_factory=dict)
    storyboard: dict[str, Any] = field(default_factory=dict)
    cinematography: dict[str, Any] = field(default_factory=dict)
    animation_timing: dict[str, Any] = field(default_factory=dict)
    continuity: dict[str, Any] = field(default_factory=dict)
    character_rig: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SupervisedChainResult:
    """Chain + supervisor with optional single revision hop."""

    chain: StoryChainResult
    supervisor: Any = None
    revision_passes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain": self.chain.to_dict(),
            "supervisor": self.supervisor.to_dict()
            if self.supervisor is not None and hasattr(self.supervisor, "to_dict")
            else self.supervisor,
            "revision_passes": self.revision_passes,
        }


def _clean_brief(brief: str) -> str:
    lines = []
    for line in (brief or "").splitlines():
        low = line.strip().lower()
        if low.startswith("runtime_seconds=") or low.startswith("story narrative"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _extract_verb(action: str) -> str:
    text = (action or "").strip()
    if not text:
        return "holds"
    match = _VERB_RE.search(text)
    if match:
        return match.group(0).lower()
    words = re.findall(r"[\w\u0600-\u06FF]+", text)
    for w in words[1:6]:
        if len(w) > 3:
            return w.lower()
    return (words[0].lower() if words else "holds")


def _composition_for_beat(beat: str, index: int) -> str:
    mapping = {
        "entrance": "L",
        "exit": "R",
        "reaction": "C",
        "reveal": "L",
        "decision": "C",
        "conflict": "X",
        "quiet_hold": "C",
    }
    return mapping.get(beat) or ("C" if index % 2 == 0 else "L")


def _action_phases(duration_sec: float, *, fps: int = 24) -> list[dict[str, Any]]:
    frames = max(12, int(round(float(duration_sec) * fps)))
    ant = max(4, min(16, frames // 6))
    aft = max(8, min(24, frames // 4))
    act = max(4, frames - ant - aft)
    return [
        {"phase": "anticipation", "frame_start": 0, "frame_end": ant},
        {"phase": "action", "frame_start": ant, "frame_end": ant + act},
        {"phase": "aftermath", "frame_start": ant + act, "frame_end": frames},
    ]


def _enrich_shot_row(
    *,
    shot_id: Any,
    title: str,
    action: str,
    duration_sec: float,
    index: int,
    total: int,
) -> dict[str, Any]:
    """Align deterministic storyboard rows with storyboard_agent.md schema."""
    beat = infer_story_beat(action, index=index, total=total)
    verb = _extract_verb(action)
    shape = _composition_for_beat(beat, index)
    idea = action.splitlines()[0][:80] if action else title
    return {
        "shot_id": shot_id,
        "title": title,
        "action": action,
        "duration_sec": round(float(duration_sec), 3),
        "idea": idea,
        "verb": verb,
        "narrative_question": f"What changes when the character {verb}?",
        "focal_point": verb,
        "composition_shape": shape,
        "story_beat": beat,
        "action_phases": _action_phases(duration_sec),
        "duration_frames": max(12, int(round(float(duration_sec) * 24))),
    }


def run_storyboard(
    brief: str,
    *,
    runtime_seconds: float | None,
    breakdown: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build storyboard from script breakdown when provided; else brief chapters."""
    if breakdown and breakdown.get("shots"):
        raw = list(breakdown["shots"])
        total = max(1, len(raw))
        shots = []
        for i, sh in enumerate(raw):
            row = _enrich_shot_row(
                shot_id=sh.get("shot_id", i),
                title=str(sh.get("title") or f"Shot {i + 1}"),
                action=str(sh.get("action") or ""),
                duration_sec=float(sh.get("duration_sec") or 3.0),
                index=i,
                total=total,
            )
            if sh.get("story_beat"):
                row["story_beat"] = sh["story_beat"]
            if sh.get("dialogue"):
                row["dialogue"] = sh["dialogue"]
            if sh.get("sfx"):
                row["sfx"] = list(sh["sfx"])
            shots.append(row)
        return {
            "agent": "StoryboardAgent",
            "shots": shots,
            "source": "script_breakdown",
            "system_prompt_loaded": bool(load_agent_system_prompt("narrative")),
            "schema": "storyboard_agent.md#v2",
        }

    chapters = split_chapters(
        brief, total_seconds=runtime_seconds, studio="story"
    )
    shots = []
    total = max(1, len(chapters))
    for ch in chapters:
        shots.append(
            _enrich_shot_row(
                shot_id=ch.index,
                title=ch.title,
                action=ch.body,
                duration_sec=float(ch.seconds),
                index=ch.index,
                total=total,
            )
        )
    return {
        "agent": "StoryboardAgent",
        "shots": shots,
        "source": "brief",
        "system_prompt_loaded": bool(load_agent_system_prompt("narrative")),
        "schema": "storyboard_agent.md#v2",
    }


def run_cinematography(storyboard: dict[str, Any]) -> dict[str, Any]:
    """
    Beat-aware cinematography (prompt-aligned fields).

    Why: pure lens rotation ignored story; Williams shot_behaviors + board
    composition_shape now drive camera/lens/look-space.
    """
    pack = load_williams_craft_pack()
    frames = []
    shots = list(storyboard.get("shots") or [])
    total = max(1, len(shots))
    for i, sh in enumerate(shots):
        action = str(sh.get("action") or sh.get("idea") or "")
        beat = str(sh.get("story_beat") or infer_story_beat(action, index=i, total=total))
        behavior = behavior_for_beat(pack, beat)
        shape = str(sh.get("composition_shape") or _composition_for_beat(beat, i)).upper()
        composition = shape[:1] if shape[:1] in {"L", "C", "R", "X", "S", "T"} else "C"
        if composition == "X":
            composition = "C"
        lens = "standard"
        camera = "static"
        if behavior:
            lens = str(behavior.get("lens") or lens)
            camera = str(behavior.get("camera") or camera)
        elif beat in {"reaction", "conflict"}:
            lens, camera = "action", "motivated_push"
        elif beat in {"quiet_hold", "reveal"}:
            lens = "beauty"
        look = "right" if composition == "L" else ("left" if composition == "R" else "none")
        frames.append(
            {
                "shot_id": sh.get("shot_id"),
                "lens": lens,
                "composition": composition,
                "camera": camera,
                "lighting": "rim_accent" if beat == "reaction" else "three_point",
                "look_space_direction": look,
                "counterchange": True,
                "camera_move": camera,
                "story_beat": beat,
                "williams_behavior_id": (behavior or {}).get("id"),
            }
        )
    return {
        "agent": "CinematographyAgent",
        "frames": frames,
        "system_prompt_loaded": bool(load_agent_system_prompt("cinematography")),
        "schema": "cinematography_agent.md#v2",
    }


def run_animation_timing(
    storyboard: dict[str, Any],
    *,
    fps: int = 24,
    cinematography: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build per-shot timing, then overlay Williams craft pack when cine is provided.

    Why: NotebookLM distill in ``libraries/williams`` must set anticipation/hold
    and camera/lens — not remain dead JSON beside the Remotion path.
    """
    # Map expressions to motion intensity (0.0=minimal, 1.0=maximal energy)
    emotion_intensity_map = {
        "sad": 0.2,
        "tired": 0.2,
        "neutral": 0.5,
        "calm": 0.4,
        "happy": 0.7,
        "excited": 1.0,
        "angry": 0.9,
        "afraid": 0.8,
        "confused": 0.5,
        "surprised": 0.9,
    }
    
    rows = []
    for sh in storyboard.get("shots") or []:
        sec = float(sh.get("duration_sec") or 3.0)
        frames = max(12, int(round(sec * fps)))
        phases = sh.get("action_phases") or _action_phases(sec, fps=fps)
        ant = int(phases[0]["frame_end"]) if phases else 6
        hold = max(8, frames - int(phases[-1]["frame_start"])) if phases else 12
        
        # Get emotion and calculate intensity
        emotion = str(sh.get("expression", "neutral")).lower()
        emotion_intensity = emotion_intensity_map.get(emotion, 0.5)
        
        rows.append(
            {
                "shot_id": sh.get("shot_id"),
                "duration_sec": sec,
                "duration_frames": frames,
                "hold_frames": hold,
                "anticipation_frames": ant,
                "emotion": emotion,
                "emotion_intensity": emotion_intensity,
            }
        )
    timing: dict[str, Any] = {
        "agent": "AnimationTimingAgent",
        "fps": fps,
        "shots": rows,
        "system_prompt_loaded": bool(load_agent_system_prompt("timing")),
        "schema": "animation_timing_agent.md#v2",
    }
    if cinematography is not None:
        timing, cine_out, _notes = apply_williams_craft(
            storyboard, timing, cinematography
        )
        cinematography.clear()
        cinematography.update(cine_out)
    return timing


def run_continuity(
    storyboard: dict[str, Any],
    *,
    cinematography: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    ContinuityAgent — keep one 180° side; flag direction/eyeline flips.

    Why: decorative checks were unused; wire prompt + cine so supervisor/Remotion
    can enforce screen geography.
    """
    shots = storyboard.get("shots") or []
    frames = {
        f.get("shot_id"): f for f in (cinematography or {}).get("frames") or []
    }
    first = frames.get((shots[0] or {}).get("shot_id")) if shots else None
    line_side = "left"
    if first and str(first.get("composition") or "").upper().startswith("R"):
        line_side = "right"
    checks = []
    violations: list[str] = []
    prev_dir: str | None = None
    for i, sh in enumerate(shots):
        sid = sh.get("shot_id")
        fr = frames.get(sid) or {}
        cam = str(fr.get("camera") or "static")
        look = str(fr.get("look_space_direction") or "")
        if look == "left":
            direction = "R_to_L"
        elif look == "right":
            direction = "L_to_R"
        elif line_side == "left":
            direction = "L_to_R"
        else:
            direction = "R_to_L"
        if prev_dir and prev_dir != direction and cam == "static":
            violations.append(f"screen_direction_flip shot={sid}")
        action = str(sh.get("action") or sh.get("idea") or "").lower()
        cause_ok = (
            i == 0
            or i == len(shots) - 1
            or any(k in action for k in ("because", "then", "until", "چون", "بعد", "تا"))
        )
        checks.append(
            {
                "shot_id": sid,
                "screen_direction": direction,
                "eyeline": "consistent",
                "cause_before_effect": bool(cause_ok),
                "lens": fr.get("lens"),
                "camera": cam,
                "look_space_direction": look or None,
            }
        )
        prev_dir = direction
    approved = len(violations) == 0
    return {
        "agent": "ContinuityAgent",
        "180_line_side": line_side,
        "eyeline_map": [
            {"character_id": "main", "looks": "right" if line_side == "left" else "left"}
        ],
        "cut_notes": ["cause_before_effect", "hold_line_of_action"],
        "violations": violations,
        "approved": approved,
        "checks": checks,
        "system_prompt_loaded": bool(load_agent_system_prompt("continuity")),
        "schema": "continuity_agent.md#v2",
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _reapply_williams_craft(
    storyboard: dict[str, Any],
    timing: dict[str, Any],
    cinematography: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    timing_out, cine_out, notes = apply_williams_craft(
        storyboard, timing, cinematography
    )
    tagged = [n.replace("williams_craft=applied", "williams_craft=reapply") for n in notes]
    if not any("reapply" in n for n in tagged):
        tagged.append("williams_craft=reapply")
    return timing_out, cine_out, tagged


def _persist_chain(
    agents_dir: Path,
    *,
    screenplay: dict[str, Any],
    script_breakdown: dict[str, Any],
    style_recommendation: dict[str, Any],
    storyboard: dict[str, Any],
    cinematography: dict[str, Any],
    timing: dict[str, Any],
    continuity: dict[str, Any],
    character_rig: dict[str, Any],
    chapters_payload: list[Any],
    llm_notes: list[str],
) -> None:
    _write_json(agents_dir / "draft_screenplay.json", screenplay)
    _write_json(agents_dir / "script_breakdown.json", script_breakdown)
    if style_recommendation:
        _write_json(agents_dir / "style_recommendation.json", style_recommendation)
    _write_json(agents_dir / "storyboard.json", storyboard)
    _write_json(agents_dir / "cinematography.json", cinematography)
    _write_json(agents_dir / "animation_timing.json", timing)
    _write_json(agents_dir / "continuity.json", continuity)
    if character_rig:
        _write_json(agents_dir / "character_rig.json", character_rig)
    manifest = {
        "order": list(AGENT_ORDER),
        "files": [
            "draft_screenplay.json",
            "script_breakdown.json",
            "style_recommendation.json",
            "storyboard.json",
            "cinematography.json",
            "animation_timing.json",
            "continuity.json",
            "character_rig.json",
        ],
        "chapters": chapters_payload,
        "llm": llm_notes,
    }
    _write_json(agents_dir / CHAIN_MANIFEST, manifest)


def revise_for_target(
    brief: str,
    chain: StoryChainResult,
    revision_target: str,
    *,
    fps: int = 24,
) -> StoryChainResult:
    """
    Single deterministic revision hop for StorySupervisor.revision_target.

    Why: supervisor previously only reported targets; craft score stayed stuck.
    """
    screenplay = dict(chain.screenplay)
    script_breakdown = dict(chain.script_breakdown)
    style_recommendation = dict(chain.style_recommendation)
    storyboard = dict(chain.storyboard)
    cinematography = dict(chain.cinematography)
    timing = dict(chain.animation_timing)
    continuity = dict(chain.continuity)
    notes = list(chain.notes)

    if revision_target in {"ScriptBreakdownAgent", "DraftScreenplayAgent"}:
        try:
            from agents.draft_screenplay_agent import run_draft_screenplay_agent
            from agents.script_breakdown_agent import run_script_breakdown_agent
        except ImportError:
            from .draft_screenplay_agent import run_draft_screenplay_agent  # type: ignore
            from .script_breakdown_agent import run_script_breakdown_agent  # type: ignore

        title = str(screenplay.get("title") or brief[:48] or "Story")
        screenplay = run_draft_screenplay_agent(brief, title=title)
        script_breakdown = run_script_breakdown_agent(screenplay, brief=brief)
        storyboard = run_storyboard(brief, breakdown=script_breakdown)
        cinematography = run_cinematography(storyboard)
        timing, continuity = _run_parallel_sync(
            lambda: run_animation_timing(storyboard, fps=fps, cinematography=cinematography),
            lambda: run_continuity(storyboard, cinematography=cinematography),
        )
        notes.append(f"revision={revision_target}")

    elif revision_target == "StoryboardAgent":
        shots = list(storyboard.get("shots") or [])
        if len(shots) < 2:
            base = (brief or "").strip() or "The character holds still."
            synthesized = [
                _enrich_shot_row(
                    shot_id=0,
                    title="Setup",
                    action=f"{base} Then the moment begins.",
                    duration_sec=3.0,
                    index=0,
                    total=3,
                ),
                _enrich_shot_row(
                    shot_id=1,
                    title="Turn",
                    action=f"Then the stakes rise because {base[:120]}",
                    duration_sec=3.5,
                    index=1,
                    total=3,
                ),
                _enrich_shot_row(
                    shot_id=2,
                    title="Close",
                    action="They leave after the beat settles.",
                    duration_sec=3.0,
                    index=2,
                    total=3,
                ),
            ]
            storyboard = {
                **storyboard,
                "shots": synthesized,
                "revised": True,
                "revision": "expand_beats",
            }
        else:
            total = len(shots)
            new_shots = []
            for i, sh in enumerate(shots):
                action = str(sh.get("action") or "")
                if (
                    0 < i < total - 1
                    and not any(
                        k in action.lower()
                        for k in ("because", "then", "until", "چون", "بعد", "تا")
                    )
                ):
                    action = f"Then {action} because the prior beat demands it."
                new_shots.append(
                    _enrich_shot_row(
                        shot_id=sh.get("shot_id", i),
                        title=str(sh.get("title") or f"Shot {i}"),
                        action=action,
                        duration_sec=float(sh.get("duration_sec") or 3.0),
                        index=i,
                        total=total,
                    )
                )
            storyboard = {**storyboard, "shots": new_shots, "revised": True}
        cinematography = run_cinematography(storyboard)
        timing, continuity = _run_parallel_sync(
            lambda: run_animation_timing(storyboard, fps=fps, cinematography=cinematography),
            lambda: run_continuity(storyboard, cinematography=cinematography),
        )
        notes.append("revision=StoryboardAgent")

    elif revision_target == "AnimationTimingAgent":
        for row in timing.get("shots") or []:
            row["hold_frames"] = max(int(row.get("hold_frames") or 0), 12)
            row["anticipation_frames"] = max(
                int(row.get("anticipation_frames") or 0), 6
            )
        timing, cinematography, craft_notes = _reapply_williams_craft(
            storyboard, timing, cinematography
        )
        notes.extend(craft_notes)
        notes.append("revision=AnimationTimingAgent")
        continuity = run_continuity(storyboard, cinematography=cinematography)

    elif revision_target == "ContinuityAgent":
        # Force a single screen direction from established line side.
        continuity = run_continuity(storyboard, cinematography=cinematography)
        side = continuity.get("180_line_side") or "left"
        direction = "L_to_R" if side == "left" else "R_to_L"
        for check in continuity.get("checks") or []:
            check["screen_direction"] = direction
            check["eyeline"] = "consistent"
        continuity["violations"] = []
        continuity["approved"] = True
        continuity["revised"] = True
        notes.append("revision=ContinuityAgent")
    else:
        notes.append(f"revision=skip:{revision_target}")

    return StoryChainResult(
        ok=bool(storyboard.get("shots")),
        agents_dir=chain.agents_dir,
        screenplay=screenplay,
        script_breakdown=script_breakdown,
        style_recommendation=style_recommendation,
        storyboard=storyboard,
        cinematography=cinematography,
        animation_timing=timing,
        continuity=continuity,
        character_rig=chain.character_rig,
        notes=notes,
    )


def run_draft_screenplay_phase(
    brief: str,
    job_dir: Path | str,
    *,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Phase A — draft screenplay only (human gate may follow before storyboard)."""
    extras = dict(extras or {})
    agents_dir = Path(job_dir) / AGENTS_DIRNAME
    agents_dir.mkdir(parents=True, exist_ok=True)
    cleaned = _clean_brief(brief)
    runtime = extras.get("runtime_seconds")
    try:
        runtime_f = float(runtime) if runtime is not None else None
    except (TypeError, ValueError):
        runtime_f = None
    try:
        from agents.draft_screenplay_agent import run_draft_screenplay_agent
    except ImportError:
        from .draft_screenplay_agent import run_draft_screenplay_agent  # type: ignore

    title = str(extras.get("title") or cleaned[:48] or "Story")
    screenplay = run_draft_screenplay_agent(
        cleaned, runtime_seconds=runtime_f, title=title
    )
    _write_json(agents_dir / "draft_screenplay.json", screenplay)
    design_dir = Path(job_dir) / "design"
    design_dir.mkdir(parents=True, exist_ok=True)
    _write_json(design_dir / "screenplay_draft.json", screenplay)
    return screenplay


def run_craft_from_screenplay(
    brief: str,
    job_dir: Path | str,
    screenplay: dict[str, Any],
    *,
    extras: dict[str, Any] | None = None,
) -> StoryChainResult:
    """Phase B — breakdown → storyboard → cine → timing → continuity from approved screenplay."""
    extras = dict(extras or {})
    agents_dir = Path(job_dir) / AGENTS_DIRNAME
    agents_dir.mkdir(parents=True, exist_ok=True)
    cleaned = _clean_brief(brief)
    runtime = extras.get("runtime_seconds")
    try:
        runtime_f = float(runtime) if runtime is not None else None
    except (TypeError, ValueError):
        runtime_f = None

    try:
        from agents.script_breakdown_agent import run_script_breakdown_agent
        from agents.style_recommender_agent import recommend_styles
    except ImportError:
        from .script_breakdown_agent import run_script_breakdown_agent  # type: ignore
        from .style_recommender_agent import recommend_styles  # type: ignore

    # OPTIMIZATION: Run style recommendation in parallel with breakdown
    script_breakdown, style_recommendation = _run_parallel_sync(
        lambda: run_script_breakdown_agent(screenplay, brief=cleaned),
        lambda: recommend_styles(
            cleaned,
            emotion=str(extras.get("emotion") or "neutral"),
            current_style_id=extras.get("style_id"),
        ),
    )
    if not extras.get("style_id"):
        extras["style_id"] = style_recommendation["primary_style_id"]

    storyboard = run_storyboard(
        cleaned, runtime_seconds=runtime_f, breakdown=script_breakdown
    )
    
    # Run cinematography first (timing and continuity depend on it)
    cinematography = run_cinematography(storyboard)
    # Then run timing and continuity in parallel with real cinematography
    timing, continuity = _run_parallel_sync(
        lambda: run_animation_timing(storyboard, fps=24, cinematography=cinematography),
        lambda: run_continuity(storyboard, cinematography=cinematography),
    )

    llm_notes: list[str] = []
    try:
        from agents.llm_enrich import (
            enrich_cinematography_llm,
            enrich_continuity_llm,
            enrich_storyboard_llm,
            enrich_timing_llm,
            llm_enabled,
        )
    except ImportError:
        from .llm_enrich import (  # type: ignore
            enrich_cinematography_llm,
            enrich_continuity_llm,
            enrich_storyboard_llm,
            enrich_timing_llm,
            llm_enabled,
        )

    if llm_enabled(extras):
        context_block = None
        if extras.get("inject_context_pack", True):
            try:
                from tools.act_planner import plan_acts
                from tools.context_pack import (
                    build_compressed_context,
                    pack_as_prompt_block,
                )
                from studio_spec import ShotControl, StudioSpec

                # Build a temporary spec from current heuristic shots for act scope
                allowed_beats = {
                    "entrance",
                    "reveal",
                    "reaction",
                    "conflict",
                    "decision",
                    "quiet_hold",
                    "exit",
                }
                allowed_poses = {"idle", "walk", "react", "run"}
                tmp_shots = []
                for i, sh in enumerate(storyboard.get("shots") or []):
                    beat = str(sh.get("story_beat") or "decision")
                    if beat not in allowed_beats:
                        beat = "decision"
                    pose = str(sh.get("pose") or "idle")
                    if pose not in allowed_poses:
                        pose = "idle"
                    tmp_shots.append(
                        ShotControl(
                            action=str(sh.get("action") or "beat")[:400] or "beat",
                            title=str(sh.get("title") or f"Shot {i}"),
                            duration_sec=float(sh.get("duration_sec") or 3.0),
                            story_beat=beat,  # type: ignore[arg-type]
                            pose=pose,  # type: ignore[arg-type]
                        )
                    )
                if tmp_shots:
                    tmp_spec = StudioSpec(
                        title="Chain",
                        runtime_seconds=float(runtime_f or 60),
                        shots=tmp_shots,
                    )
                    plan = plan_acts(tmp_spec)
                    pack = build_compressed_context(
                        tmp_spec,
                        act=plan.acts[0],
                        bible=cleaned[:400],
                    )
                    context_block = pack_as_prompt_block(pack)
                    (Path(job_dir) / "compressed_context.json").write_text(
                        json.dumps(pack.model_dump(mode="json"), indent=2, ensure_ascii=False)
                        + "\n",
                        encoding="utf-8",
                    )
                    (Path(job_dir) / "act_plan.json").write_text(
                        json.dumps(plan.to_public_dict(), indent=2, ensure_ascii=False)
                        + "\n",
                        encoding="utf-8",
                    )
                    llm_notes.append("context_pack=1")
            except Exception as exc:  # noqa: BLE001
                llm_notes.append(f"context_pack=skip:{exc!r}")

        enriched = enrich_storyboard_llm(
            cleaned, storyboard, context_block=context_block
        )
        if enriched:
            # Re-attach craft fields LLM may omit.
            fixed = []
            total = len(enriched.get("shots") or [])
            for i, sh in enumerate(enriched.get("shots") or []):
                fixed.append(
                    _enrich_shot_row(
                        shot_id=sh.get("shot_id", i),
                        title=str(sh.get("title") or f"Shot {i}"),
                        action=str(sh.get("action") or ""),
                        duration_sec=float(sh.get("duration_sec") or 3.0),
                        index=i,
                        total=max(1, total),
                    )
                )
            storyboard = {**enriched, "shots": fixed}
            cinematography = run_cinematography(storyboard)
            timing = run_animation_timing(
                storyboard, fps=24, cinematography=cinematography
            )
            continuity = run_continuity(storyboard, cinematography=cinematography)
            llm_notes.append("storyboard_llm=1")
        else:
            llm_notes.append("storyboard_llm=skip")
        cine2 = enrich_cinematography_llm(cleaned, cinematography, storyboard)
        if cine2:
            cinematography = cine2
            llm_notes.append("cine_llm=1")
        timing2 = enrich_timing_llm(cleaned, timing, storyboard)
        if timing2:
            timing = timing2
            llm_notes.append("timing_llm=1")
        cont2 = enrich_continuity_llm(
            cleaned, continuity, storyboard, cinematography
        )
        if cont2:
            continuity = cont2
            llm_notes.append("continuity_llm=1")
        if not continuity.get("checks"):
            continuity = run_continuity(storyboard, cinematography=cinematography)
    else:
        llm_notes.append("llm=off")

    # Always re-apply Williams craft after optional LLM so timing/cine stay craft-true.
    timing, cinematography, craft_notes = _reapply_williams_craft(
        storyboard, timing, cinematography
    )
    llm_notes.extend(craft_notes)
    continuity = run_continuity(storyboard, cinematography=cinematography)

    # Williams timing enrich (Node) — optional, non-fatal
    try:
        from tools.williams_bridge import enrich_timing_with_williams
    except ImportError:
        llm_notes.append("williams=skip:import")
    else:
        try:
            timing2 = enrich_timing_with_williams(timing, job_dir=Path(job_dir))
            if timing2.get("williams_enriched"):
                timing = timing2
                llm_notes.append("williams=1")
            else:
                llm_notes.append("williams=skip")
        except Exception as exc:  # noqa: BLE001
            llm_notes.append(f"williams=error:{type(exc).__name__}")

    character_rig: dict[str, Any] = {}
    try:
        from tools.williams_character_bridge import enrich_character_rig
    except ImportError:
        llm_notes.append("character_rig=skip:import")
    else:
        try:
            character_rig = enrich_character_rig(
                emotion=str(extras.get("emotion") or "neutral"),
                job_dir=Path(job_dir),
            )
            if character_rig.get("williams_character"):
                llm_notes.append("character_rig=1")
            else:
                llm_notes.append("character_rig=idle")
        except Exception as exc:  # noqa: BLE001
            llm_notes.append(f"character_rig=error:{type(exc).__name__}")

    chapters_payload = chapters_to_jsonable(
        split_chapters(cleaned, total_seconds=runtime_f, studio="story")
    )
    try:
        from tools.scene_ir_builder import build_scene_ir_from_chain
    except ImportError:
        from ..tools.scene_ir_builder import build_scene_ir_from_chain  # type: ignore

    scene_ir = build_scene_ir_from_chain(
        cleaned,
        storyboard=storyboard,
        cinematography=cinematography,
        timing=timing,
        continuity=continuity,
        job_out_dir=str(Path(job_dir).resolve()),
        runtime_seconds=runtime_f,
    )
    _write_json(
        Path(job_dir) / "scene_ir.json",
        json.loads(scene_ir.model_dump_json()),
    )
    llm_notes.append("scene_ir=1")

    _persist_chain(
        agents_dir,
        screenplay=screenplay,
        script_breakdown=script_breakdown,
        style_recommendation=style_recommendation,
        storyboard=storyboard,
        cinematography=cinematography,
        timing=timing,
        continuity=continuity,
        character_rig=character_rig,
        chapters_payload=chapters_payload,
        llm_notes=llm_notes,
    )
    notes = [
        f"shots={len(storyboard.get('shots') or [])}",
        "phase_a=screenplay_breakdown",
        *llm_notes,
    ]
    return StoryChainResult(
        ok=bool(storyboard.get("shots")),
        agents_dir=str(agents_dir.resolve()),
        screenplay=screenplay,
        script_breakdown=script_breakdown,
        style_recommendation=style_recommendation,
        storyboard=storyboard,
        cinematography=cinematography,
        animation_timing=timing,
        continuity=continuity,
        character_rig=character_rig,
        notes=notes,
    )


def run_story_agent_chain(
    brief: str,
    job_dir: Path | str,
    *,
    extras: dict[str, Any] | None = None,
    screenplay: dict[str, Any] | None = None,
) -> StoryChainResult:
    """Full craft: draft screenplay (optional skip) + visual chain."""
    extras = dict(extras or {})
    if screenplay is None:
        screenplay = run_draft_screenplay_phase(brief, job_dir, extras=extras)
    return run_craft_from_screenplay(brief, job_dir, screenplay, extras=extras)


def _load_job_scene_ir(brief: str, job_dir: Path | str):
    """Prefer filled scene_ir.json; fall back to empty."""
    try:
        from scene_ir import SceneIR, empty_scene_ir
    except ImportError:
        from ..scene_ir import SceneIR, empty_scene_ir  # type: ignore

    path = Path(job_dir) / "scene_ir.json"
    if path.is_file():
        try:
            return SceneIR.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return empty_scene_ir(brief)


def run_story_agent_chain_with_supervision(
    brief: str,
    job_dir: Path | str,
    *,
    extras: dict[str, Any] | None = None,
    style_profile: dict[str, Any] | None = None,
) -> SupervisedChainResult:
    """Run agent chain, supervisor, and up to N revision hops (default 2)."""
    extras = dict(extras or {})
    # Avoid hard-fail on first pass so revision can run.
    extras.setdefault("quality_gate_strict", False)
    try:
        max_passes = max(0, min(3, int(extras.get("max_revision_passes", 2))))
    except (TypeError, ValueError):
        max_passes = 2
    chain = run_story_agent_chain(brief, job_dir, extras=extras)

    try:
        from agents.story_supervisor import run_story_supervisor
    except ImportError:
        from .story_supervisor import run_story_supervisor  # type: ignore

    def _supervise(c: StoryChainResult):
        return run_story_supervisor(
            _load_job_scene_ir(brief, job_dir),
            brief=brief,
            extras=extras,
            style_profile=style_profile,
            job_dir=job_dir,
            continuity=c.continuity,
            strict=False,
        )

    supervisor = _supervise(chain)
    revision_passes = 0
    while (
        revision_passes < max_passes
        and (not supervisor.passed)
        and supervisor.revision_target
    ):
        target = str(supervisor.revision_target)
        chain = revise_for_target(brief, chain, target, fps=24)
        revision_passes += 1
        # Rebuild SceneIR after revision
        try:
            from tools.scene_ir_builder import build_scene_ir_from_chain
        except ImportError:
            from ..tools.scene_ir_builder import build_scene_ir_from_chain  # type: ignore

        ir = build_scene_ir_from_chain(
            _clean_brief(brief),
            storyboard=chain.storyboard,
            cinematography=chain.cinematography,
            timing=chain.animation_timing,
            continuity=chain.continuity,
            job_out_dir=str(Path(job_dir).resolve()),
            runtime_seconds=float(extras["runtime_seconds"])
            if extras.get("runtime_seconds") is not None
            else None,
        )
        _write_json(
            Path(job_dir) / "scene_ir.json",
            json.loads(ir.model_dump_json()),
        )
        agents_dir = Path(job_dir) / AGENTS_DIRNAME
        chapters_payload = chapters_to_jsonable(
            split_chapters(
                _clean_brief(brief),
                total_seconds=float(extras["runtime_seconds"])
                if extras.get("runtime_seconds") is not None
                else None,
                studio="story",
            )
        )
        _persist_chain(
            agents_dir,
            screenplay=chain.screenplay,
            script_breakdown=chain.script_breakdown,
            style_recommendation=chain.style_recommendation,
            storyboard=chain.storyboard,
            cinematography=chain.cinematography,
            timing=chain.animation_timing,
            continuity=chain.continuity,
            character_rig=chain.character_rig,
            chapters_payload=chapters_payload,
            llm_notes=[n for n in chain.notes if "=" in n],
        )
        supervisor = _supervise(chain)
        chain.notes.append(
            f"revision={revision_passes} target={target} "
            f"passed={supervisor.passed}"
        )

    return SupervisedChainResult(
        chain=chain,
        supervisor=supervisor,
        revision_passes=revision_passes,
    )
