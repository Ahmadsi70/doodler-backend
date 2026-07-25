from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Callable

from .message_types import Attachment, MessageRole, MessageStatus
from .chat_session import ChatSession
from .agent_bus import AgentBus


class ChatHub:
    def __init__(self, sessions_dir: str | Path = ".story/sessions"):
        self.sessions: dict[str, ChatSession] = {}
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.agent_bus = AgentBus()
        self._ws_connections: dict[str, set[Callable[[dict[str, Any]], None]]] = {}

    def create_session(self) -> ChatSession:
        session = ChatSession.create_welcome_session()
        self.sessions[session.id] = session
        self._save_session(session)
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        if session_id not in self.sessions:
            session_path = self.sessions_dir / f"{session_id}.json"
            if session_path.is_file():
                try:
                    session = ChatSession.load(session_path)
                    self.sessions[session_id] = session
                except Exception:
                    return None
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)
        session_path = self.sessions_dir / f"{session_id}.json"
        if session_path.is_file():
            session_path.unlink()

    async def handle_user_message(
        self,
        session_id: str,
        content: str,
    ) -> list[dict[str, Any]]:
        session = self.get_session(session_id)
        if session is None:
            return [{"type": "error", "content": "Session not found"}]

        session.add_user_message(content)
        events: list[dict[str, Any]] = [{
            "type": "user_message",
            "session_id": session_id,
            "content": content,
            "timestamp": time.time(),
        }]

        if content.startswith("/"):
            cmd_events = await self._handle_command(session, content)
            events.extend(cmd_events)
        else:
            pipeline_events = await self.agent_bus.run_auto_pipeline(content, session)
            events.extend(pipeline_events)

        self._save_session(session)
        return events

    async def handle_agent_call(
        self,
        session_id: str,
        agent_name: str,
        content: str,
    ) -> list[dict[str, Any]]:
        session = self.get_session(session_id)
        if session is None:
            return [{"type": "error", "content": "Session not found"}]

        result = await self.agent_bus.run_agent(agent_name, content, session)
        self._save_session(session)
        return result

    async def _handle_command(
        self,
        session: ChatSession,
        command: str,
    ) -> list[dict[str, Any]]:
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        events: list[dict[str, Any]] = []

        if cmd == "/agents":
            agents = self.agent_bus.list_agents()
            msg = "**ایجنت‌های موجود:**\n\n"
            for a in agents:
                status = session.get_agent_state(a["name"]).value
                msg += f"- **{a['name']}** ({a['mode']}): {a['description']} — وضعیت: {status}\n"
            session.add_system_message(msg)
            events.append({"type": "system_message", "session_id": session.id, "content": msg})

        elif cmd == "/agent" and args:
            agent_name = args.split()[0]
            agent_prompt = args[len(agent_name):].strip()
            agent = self.agent_bus.get_agent(agent_name)
            if agent is None:
                session.add_system_message(f"❌ ایجنت '{agent_name}' یافت نشد.")
                events.append({"type": "system_message", "session_id": session.id, "content": f"Agent '{agent_name}' not found"})
            else:
                session.add_system_message(f"🔄 در حال اجرای {agent_name}...")
                events.append({"type": "agent_start", "agent": agent_name, "session_id": session.id})
                result = await self.agent_bus.run_agent(agent_name, agent_prompt or session.brief, session)
                events.extend(result)

        elif cmd == "/run":
            session.add_system_message("🔄 اجرای خودکار همه ایجنت‌ها...")
            events.append({"type": "pipeline_start", "session_id": session.id})
            result = await self.agent_bus.run_auto_pipeline(session.brief, session)
            events.extend(result)
            session.add_system_message("✅ همه ایجنت‌ها اجرا شدند.")
            events.append({"type": "pipeline_done", "session_id": session.id})

        elif cmd == "/code":
            last_code = self._get_latest_code(session)
            if last_code:
                session.add_agent_message(
                    "کد Remotion تولید شده:",
                    agent_name="render_agent",
                    attachments=[Attachment(type="code", label="StoryNarrative.tsx", content=last_code, language="typescript")],
                )
            else:
                session.add_system_message("هنوز کدی تولید نشده است.")

        elif cmd == "/character":
            char_path = session.metadata.get("character_path")
            char_name = session.metadata.get("character_filename", "")
            if char_path and Path(char_path).is_file():
                session.add_system_message(
                    f"🖼 **کاراکتر فعلی:** `{char_name}` در `{char_path}`\n"
                    "برای آپلود کاراکتر جدید از API استفاده کنید:\n"
                    "```\n"
                    f"curl -F \"file=@path/to/image.png\" http://localhost:8000/api/upload/{session.id}\n"
                    "```",
                    phase="character",
                )
            else:
                session.add_system_message(
                    "🖼 هنوز کاراکتری آپلود نشده.\n"
                    "برای آپلود:\n"
                    "```\n"
                    f"curl -F \"file=@path/to/image.png\" http://localhost:8000/api/upload/{session.id}\n"
                    "```\n"
                    "یا از فرم آپلود در صفحه استفاده کنید.",
                    phase="character",
                    needs_reply=False,
                )

        elif cmd == "/export":
            session.add_system_message("📦 در حال آماده‌سازی پروژه برای دانلود...")
            events.append({"type": "export", "session_id": session.id})

        elif cmd == "/reset":
            session.messages.clear()
            session.brief = ""
            session.current_phase = "idle"
            session.agent_states.clear()
            session.add_system_message("🔄 همه چیز ریست شد. پروژه جدید شروع کنید.")

        else:
            session.add_system_message(f"⚠ دستور ناشناخته: {cmd}. از /agents برای دیدن دستورات استفاده کنید.")

        return events

    def _get_latest_code(self, session: ChatSession) -> str | None:
        for m in reversed(session.messages):
            for a in m.attachments:
                if a.type == "code" and a.language == "typescript":
                    return a.content
        return None

    def connect_ws(self, session_id: str, callback: Callable[[dict[str, Any]], None]) -> None:
        if session_id not in self._ws_connections:
            self._ws_connections[session_id] = set()
        self._ws_connections[session_id].add(callback)

        def on_bus_event(event: dict[str, Any]) -> None:
            if event.get("session_id") == session_id:
                try:
                    callback(event)
                except Exception:
                    pass

        self.agent_bus.on_message(on_bus_event)

    def disconnect_ws(self, session_id: str, callback: Callable[[dict[str, Any]], None]) -> None:
        if session_id in self._ws_connections:
            self._ws_connections[session_id].discard(callback)

    def _save_session(self, session: ChatSession) -> None:
        session_path = self.sessions_dir / f"{session.id}.json"
        session.save(session_path)

    def broadcast_to_session(self, session_id: str, event: dict[str, Any]) -> None:
        if session_id in self._ws_connections:
            for cb in self._ws_connections[session_id]:
                try:
                    cb(event)
                except Exception:
                    pass
