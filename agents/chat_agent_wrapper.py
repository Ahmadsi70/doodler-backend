from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from chat.message_types import Attachment, MessageStatus
from chat.chat_session import ChatSession
from chat.agent_bus import AgentBus, AgentMode


def _extract_agent_json(session: ChatSession, agent_name: str) -> dict[str, Any]:
    msg = session.get_last_agent_message(agent_name)
    if msg and msg.attachments:
        for att in msg.attachments:
            if att.type == "json":
                return json.loads(att.content)
    return {}

def _extract_all_agent_jsons(session: ChatSession) -> dict[str, Any]:
    """Collect all agent JSON outputs from session attachments into a dict keyed by agent name."""
    out = {}
    for m in session.messages:
        if m.role.value == "agent" and m.attachments:
            for att in m.attachments:
                if att.type == "json":
                    try:
                        out[m.agent_name] = json.loads(att.content)
                    except Exception:
                        pass
    return out


def _register_draft_screenplay(bus: AgentBus) -> None:
    from agents.draft_screenplay_agent import run_draft_screenplay_agent

    async def handler(user_input: str, session: ChatSession) -> list[dict[str, Any]]:
        result = run_draft_screenplay_agent(
            user_input or session.brief,
            title=session.metadata.get("title", "Story"),
        )
        session.current_phase = "screenplay"
        scenes_md = result.get("screenplay_md", "")
        session.add_agent_message(
            f"**فیلمنامه پیشنهادی:**\n\n{scenes_md}",
            agent_name="DraftScreenplay",
            attachments=[Attachment(
                type="json", label="screenplay.json",
                content=json.dumps(result, indent=2, ensure_ascii=False),
                language="json",
            )],
            needs_reply=True,
            suggestions=["تأیید", "ویرایش فیلمنامه", "/agent ScriptBreakdown"],
        )
        return [{"type": "agent_output", "agent": "DraftScreenplay", "phase": "screenplay"}]

    bus.register(
        "DraftScreenplay", "تبدیل brief به فیلمنامه اولیه با صحنه‌ها",
        handler, phase="screenplay", mode=AgentMode.AUTO,
    )


def _register_script_breakdown(bus: AgentBus) -> None:
    from agents.script_breakdown_agent import run_script_breakdown_agent

    async def handler(user_input: str, session: ChatSession) -> list[dict[str, Any]]:
        screenplay = _extract_agent_json(session, "DraftScreenplay")
        if screenplay.get("scenes"):
            result = run_script_breakdown_agent(screenplay)
        else:
            result = run_script_breakdown_agent({"scenes": []}, brief=user_input or session.brief)
        session.current_phase = "breakdown"
        shots = result.get("shots", [])
        lines = "\n\n".join(
            f"**شات {s.get('shot_id', i+1)}:** {s.get('action', '')} "
            f"(دوربین: {s.get('camera', 'static')}, لنز: {s.get('lens', 'standard')})"
            for i, s in enumerate(shots)
        )
        session.add_agent_message(
            f"**شات‌های استخراج شده:**\n\n{lines}",
            agent_name="ScriptBreakdown",
            attachments=[Attachment(
                type="json", label="breakdown.json",
                content=json.dumps(result, indent=2, ensure_ascii=False),
                language="json",
            )],
            needs_reply=True,
            suggestions=["تأیید", "ویرایش شات‌ها", "/agent Storyboard"],
        )
        return [{"type": "agent_output", "agent": "ScriptBreakdown", "phase": "breakdown"}]

    bus.register(
        "ScriptBreakdown", "شکستن فیلمنامه به شات‌های مجزا با دوربین و لنز",
        handler, phase="breakdown", dependencies=["DraftScreenplay"], mode=AgentMode.AUTO,
    )


def _register_storyboard(bus: AgentBus) -> None:
    from agents.story_chain import run_storyboard

    async def handler(user_input: str, session: ChatSession) -> list[dict[str, Any]]:
        breakdown = _extract_agent_json(session, "ScriptBreakdown")
        result = run_storyboard(
            user_input or session.brief,
            runtime_seconds=None,
            breakdown=breakdown if breakdown.get("shots") else None,
        )
        session.current_phase = "storyboard"
        shots = result.get("shots", [])
        lines = "\n\n".join(
            f"**شات {s.get('shot_id', i+1)}:** {s.get('idea', '')} "
            f"[{s.get('story_beat', '')}] ترکیب: {s.get('composition_shape', 'C')}"
            for i, s in enumerate(shots)
        )
        session.add_agent_message(
            f"**استوری‌بورد:**\n\n{lines}",
            agent_name="Storyboard",
            attachments=[Attachment(
                type="json", label="storyboard.json",
                content=json.dumps(result, indent=2, ensure_ascii=False),
                language="json",
            )],
            needs_reply=True,
            suggestions=["تأیید", "/agent Cinematography", "/agent AnimationTiming"],
        )
        return [{"type": "agent_output", "agent": "Storyboard", "phase": "storyboard"}]

    bus.register(
        "Storyboard", "ایجاد استوری‌بورد با ضرب‌آهنگ داستانی (entrance, reaction, ...)",
        handler, phase="storyboard", dependencies=["ScriptBreakdown"], mode=AgentMode.AUTO,
    )


def _register_cinematography(bus: AgentBus) -> None:
    from agents.story_chain import run_cinematography

    async def handler(user_input: str, session: ChatSession) -> list[dict[str, Any]]:
        board = _extract_agent_json(session, "Storyboard")
        result = run_cinematography(board)
        session.current_phase = "cinematography"
        frames = result.get("frames", [])
        lines = "\n".join(
            f"- شات {f.get('shot_id', i+1)}: لنز {f.get('lens', 'standard')} | "
            f"دوربین {f.get('camera', 'static')} | نور {f.get('lighting', 'three_point')}"
            for i, f in enumerate(frames)
        )
        session.add_agent_message(
            f"**سینماتوگرافی:**\n\n{lines}",
            agent_name="Cinematography",
            attachments=[Attachment(
                type="json", label="cinematography.json",
                content=json.dumps(result, indent=2, ensure_ascii=False),
                language="json",
            )],
            suggestions=["تأیید", "/agent AnimationTiming"],
        )
        return [{"type": "agent_output", "agent": "Cinematography", "phase": "cinematography"}]

    bus.register(
        "Cinematography", "انتخاب لنز، حرکت دوربین، نورپردازی و ترکیب‌بندی",
        handler, phase="cinematography", dependencies=["Storyboard"], mode=AgentMode.AUTO,
    )


def _register_animation_timing(bus: AgentBus) -> None:
    from agents.story_chain import run_animation_timing

    async def handler(user_input: str, session: ChatSession) -> list[dict[str, Any]]:
        cine = _extract_agent_json(session, "Cinematography")
        result = run_animation_timing(cine)
        session.current_phase = "timing"
        shots = result.get("shots", [])
        lines = "\n".join(
            f"- شات {s.get('shot_id', i+1)}: {s.get('duration_sec', 3)}s "
            f"({s.get('duration_frames', 72)} فریم) | "
            f"Anticipation: {s.get('anticipation_frames', 6)} | "
            f"Hold: {s.get('hold_frames', 12)}"
            for i, s in enumerate(shots)
        )
        session.add_agent_message(
            f"**تایمینگ انیمیشن (قوانین Williams):**\n\n{lines}",
            agent_name="AnimationTiming",
            attachments=[Attachment(
                type="json", label="timing.json",
                content=json.dumps(result, indent=2, ensure_ascii=False),
                language="json",
            )],
            suggestions=["تأیید", "/agent Continuity"],
        )
        return [{"type": "agent_output", "agent": "AnimationTiming", "phase": "timing"}]

    bus.register(
        "AnimationTiming", "محاسبه تایمینگ فریم‌ها با قوانین Williams",
        handler, phase="timing", dependencies=["Cinematography"], mode=AgentMode.AUTO,
    )


def _register_continuity(bus: AgentBus) -> None:
    from agents.story_chain import run_continuity

    async def handler(user_input: str, session: ChatSession) -> list[dict[str, Any]]:
        board = _extract_agent_json(session, "Storyboard")
        result = run_continuity(board)
        session.current_phase = "continuity"
        violations = result.get("violations", [])
        v_text = "\n".join(f"- {v}" for v in violations) if violations else "✅ هیچ مورد نقضی یافت نشد."
        session.add_agent_message(
            f"**بررسی پیوستگی (قانون ۱۸۰ درجه):**\n\n{v_text}",
            agent_name="Continuity",
            attachments=[Attachment(
                type="json", label="continuity.json",
                content=json.dumps(result, indent=2, ensure_ascii=False),
                language="json",
            )],
            suggestions=["تأیید", "/agent RenderAgent", "/agent Locomotion"],
        )
        return [{"type": "agent_output", "agent": "Continuity", "phase": "continuity"}]

    bus.register(
        "Continuity", "بررسی پیوستگی خط داستانی و قانون ۱۸۰ درجه",
        handler, phase="continuity", dependencies=["AnimationTiming"], mode=AgentMode.AUTO,
    )


def _register_render_agent(bus: AgentBus) -> None:
    from tools.remotion_emitter import write_story_composition_props
    from agents.render_agent import run_render_agent as _run_render_agent

    async def handler(user_input: str, session: ChatSession) -> list[dict[str, Any]]:
        board = _extract_agent_json(session, "Storyboard")
        cine = _extract_agent_json(session, "Cinematography")
        timing = _extract_agent_json(session, "AnimationTiming")
        cont = _extract_agent_json(session, "Continuity")

        out = Path(tempfile.mkdtemp(prefix="story_render_"))
        write_story_composition_props(
            out,
            storyboard=board,
            cinematography=cine,
            timing=timing,
            continuity=cont,
            character_path=session.metadata.get("character_path"),
            title=session.metadata.get("title", "Story"),
            frame_pipeline_state=session.metadata.get("frame_pipeline_state"),
        )

        result = _run_render_agent(out, mode="code_only", title=session.metadata.get("title", "Story"))
        session.current_phase = "render"
        events: list[dict[str, Any]] = []

        if result.ok and result.code_files:
            attachments = []
            for f in result.code_files:
                p = Path(f)
                if p.is_file():
                    lang = "powershell" if f.endswith(".ps1") else "bash" if f.endswith(".sh") else "json" if f.endswith(".json") else "markdown"
                    attachments.append(Attachment(
                        type="code", label=p.name,
                        content=p.read_text(encoding="utf-8"),
                        language=lang,
                    ))

            story_props_file = out / "story_props.json"
            if story_props_file.is_file():
                session.metadata["story_props_path"] = str(story_props_file.resolve())
                session.metadata["story_props"] = json.loads(story_props_file.read_text(encoding="utf-8"))

            session.add_agent_message(
                "**✅ کد Remotion ساخته شد!**\n\n"
                "فایل‌های تولید شده:\n"
                + "\n".join(f"- `{Path(f).name}`" for f in result.code_files)
                + "\n\nدستور اجرا:\n```\n" + (result.run_command or "") + "\n```",
                agent_name="RenderAgent",
                status=MessageStatus.DONE,
                attachments=attachments,
                suggestions=["📋 کپی کد", "📦 دانلود پروژه", "/code", "/export", "📊 ویرایشگر"],
            )
            events.append({
                "type": "agent_output", "agent": "RenderAgent", "phase": "render",
                "code_files": result.code_files,
                "run_command": result.run_command,
                "story_props": str(out / "story_props.json"),
            })
        else:
            session.add_agent_message(
                f"❌ خطا در تولید کد: {result.error}",
                agent_name="RenderAgent", status=MessageStatus.ERROR, error=result.error,
            )
            events.append({"type": "agent_error", "agent": "RenderAgent", "error": result.error})

        return events

    bus.register(
        "RenderAgent", "تولید کد نهایی Remotion (story_props.json + اسکریپت رندر)",
        handler, phase="render", dependencies=["Continuity"],
        mode=AgentMode.MANUAL,
    )


def _register_rubber_duck(bus: AgentBus) -> None:
    async def handler(user_input: str, session: ChatSession) -> list[dict[str, Any]]:
        session.add_agent_message(
            f"🦆 **RubberDuck:** سوال خوبی پرسیدی!\n\n"
            f"«{user_input}»\n\n"
            f"بذار فکر کنم... آیا این بخش از داستان برای مخاطب واضح است؟",
            agent_name="RubberDuck", needs_reply=True,
            suggestions=["بله", "نه، توضیح می‌دهم"],
        )
        return [{"type": "agent_output", "agent": "RubberDuck", "phase": "review"}]

    bus.register(
        "RubberDuck", "بازبینی خلاقانه داستان با سوالات هوشمند",
        handler, phase="review", mode=AgentMode.MANUAL,
    )


def _register_frame_pipeline(bus: AgentBus) -> None:
    from agents.frame_pipeline import build_chart_input, run_frame_pipeline

    async def handler(user_input: str, session: ChatSession) -> list[dict[str, Any]]:
        all_json = _extract_all_agent_jsons(session)
        # Collect shot data from the latest available agent output
        board = all_json.get("Storyboard", all_json.get("Cinematography", all_json.get("AnimationTiming", {})))
        shots = board.get("shots", board.get("frames", []))
        shots_in = []
        for s in shots:
            sid = s.get("shot_id", s.get("shotId", 0))
            shots_in.append({
                "shotId": sid,
                "action": s.get("action") or s.get("idea") or "",
                "storyBeat": s.get("story_beat") or s.get("storyBeat") or "",
                "durationFrames": s.get("duration_frames") or s.get("durationFrames") or 72,
                "anticipationFrames": s.get("anticipation_frames") or s.get("anticipationFrames") or 6,
                "holdFrames": s.get("hold_frames") or s.get("holdFrames") or 12,
                "camera": s.get("camera") or "static",
                "cameraMove": s.get("camera_move") or s.get("cameraMove") or {},
                "craftHints": s.get("craftHints") or {"rig": {"pose": "idle", "expression": "neutral"}},
                "dialogue": s.get("dialogue") or "",
                "voPath": s.get("vo_path") or s.get("voPath") or "",
                "sfx": list(s.get("sfx") or []),
            })

        if not shots_in:
            session.add_agent_message(
                "❌ داده شات برای pipeline فریم یافت نشد. ابتدا Storyboard را اجرا کنید.",
                agent_name="FramePipeline", status=MessageStatus.ERROR,
            )
            return [{"type": "agent_error", "agent": "FramePipeline", "error": "No shot data"}]

        chart_input = build_chart_input(shots_in)
        session.current_phase = "frame_details"

        def broadcast(event: dict[str, Any]) -> None:
            bus._broadcast(event)

        state, events = run_frame_pipeline(
            chart_input,
            broadcast=broadcast,
            session_id=session.id,
        )

        # Store pipeline state in session metadata for RenderAgent
        session.metadata["frame_pipeline_state"] = state.to_dict()

        artifacts_summary = []
        if state.performance_chart:
            artifacts_summary.append(f"- PerformanceChart: {len(state.performance_chart.get('shots') or [])} shots")
        if state.contact_lock:
            artifacts_summary.append(f"- ContactLock: {len(state.contact_lock.get('contacts') or [])} contacts")
        if state.camera_curves:
            artifacts_summary.append(f"- CameraCurves: {len(state.camera_curves.get('curves') or [])} curves")
        if state.acting_lead:
            artifacts_summary.append(f"- ActingLead: {len(state.acting_lead.get('markers') or [])} markers")

        session.add_agent_message(
            "**🔄 Pipeline فریم کامل شد**\n\n"
            + "\n".join(artifacts_summary)
            + ("\n\n⚠ خطا: " + state.error if state.error else ""),
            agent_name="FramePipeline",
            attachments=[
                Attachment(type="json", label="frame_pipeline_state.json",
                           content=json.dumps(state.to_dict(), indent=2, ensure_ascii=False),
                           language="json"),
            ],
            needs_reply=False,
            suggestions=["/agent RenderAgent", "📊 ویرایشگر"],
        )
        events.append({"type": "agent_output", "agent": "FramePipeline", "phase": "frame_details"})
        return events

    bus.register(
        "FramePipeline",
        "اجرای ۱۰ ایجنت فریم (PerformanceChart, Locomotion, ContactLock, ActingLead, ...) با پخش تل‌متری",
        handler, phase="frame_details", dependencies=["Continuity"],
        mode=AgentMode.AUTO,
    )


def _register_art_director(bus: AgentBus) -> None:
    from agents.art_director_agent import run_art_director_agent

    async def handler(user_input: str, session: ChatSession) -> list[dict[str, Any]]:
        board = _extract_agent_json(session, "Storyboard")
        fstate = session.metadata.get("frame_pipeline_state") or {}
        char_desc = session.metadata.get("character_description", "")
        char_analysis = session.metadata.get("character_analysis")

        # Enrich board shots with frame-level detail from pipeline state
        chart_input = fstate.get("chart_input") or []
        pc_shots = (fstate.get("performance_chart") or {}).get("shots") or []
        pc_by_id = {s.get("shot_id"): s for s in pc_shots}
        enhanced_shots = []
        for s in (board.get("shots") or []):
            sid = s.get("shot_id", s.get("shotId"))
            pc = pc_by_id.get(sid) or {}
            enhanced_shots.append({
                **s,
                "pose": pc.get("pose", s.get("pose", "idle")),
                "expression": pc.get("expression", s.get("expression", "neutral")),
                "action": pc.get("action", s.get("action", "")),
            })
        board = {**board, "shots": enhanced_shots}

        result = run_art_director_agent(
            board,
            character_description=char_desc,
            character_analysis=char_analysis,
            style_id=session.metadata.get("style_id", "cinematic"),
        )

        session.metadata["art_director"] = result
        shots = result.get("shots") or []
        lines = "\n\n".join(
            f"**شات {s.get('shotId')}:** (pose: {s.get('subject', '')[:60]}...)\n"
            f"🎨 MJ: {s.get('prompts', {}).get('midjourney', '')[:120]}...\n"
            f"🤖 SDXL: {s.get('prompts', {}).get('sdxl', '')[:120]}..."
            for s in shots
        )

        session.add_agent_message(
            f"**🎨 ArtDirector — پرامپت‌های تصویری**\n\n"
            f"سبک: {result.get('style_id')} | "
            f"کاراکتر: {result.get('character_name')} | "
            f"Seed: {result.get('character_seed')}\n\n"
            f"پالت رنگ: {', '.join(result.get('palette') or [])}\n\n"
            f"{lines}",
            agent_name="ArtDirector",
            attachments=[Attachment(
                type="json", label="art_director.json",
                content=json.dumps(result, indent=2, ensure_ascii=False),
                language="json",
            )],
            needs_reply=True,
            suggestions=["تغییر سبک", "تغییر Seed", "/agent RenderAgent"],
        )
        return [{"type": "agent_output", "agent": "ArtDirector", "phase": "art_director"}]

    bus.register(
        "ArtDirector",
        "تولید پرامپت‌های T2I (Midjourney, SDXL, DALL-E 3) با جزئیات فریم از FramePipeline",
        handler, phase="art_director", dependencies=["FramePipeline"],
        mode=AgentMode.MANUAL,
    )


def register_all_agents(bus: AgentBus) -> None:
    _register_draft_screenplay(bus)
    _register_script_breakdown(bus)
    _register_storyboard(bus)
    _register_cinematography(bus)
    _register_animation_timing(bus)
    _register_continuity(bus)
    _register_frame_pipeline(bus)
    _register_render_agent(bus)
    _register_art_director(bus)
    _register_rubber_duck(bus)
