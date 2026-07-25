from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse
except ImportError:
    raise ImportError("fastapi not installed. Install with: pip install fastapi uvicorn")

from chat.chat_hub import ChatHub
from chat.chat_session import ChatSession
from agents.chat_agent_wrapper import register_all_agents

# ── Load .env file ──────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.is_file():
        load_dotenv(dotenv_path=str(_env_path), override=False)
except Exception:
    pass

chat_hub = ChatHub()


@asynccontextmanager
async def lifespan(app: FastAPI):
    register_all_agents(chat_hub.agent_bus)
    print(f"Story Studio Chat API started — {len(chat_hub.agent_bus.list_agents())} agents registered")
    yield

app = FastAPI(
    title="Story Studio Chat API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "name": "Story Studio Chat API",
        "version": "0.1.0",
        "agents": len(chat_hub.agent_bus.list_agents()),
    }


@app.get("/api/health")
async def health():
    return {"status": "ok", "sessions": len(chat_hub.sessions)}


@app.post("/api/session")
async def create_session():
    session = chat_hub.create_session()
    return {
        "session_id": session.id,
        "message": "Session created",
        "session": session.to_dict(),
    }


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    session = chat_hub.get_session(session_id)
    if session is None:
        return {"error": "Session not found"}, 404
    return session.to_dict()


@app.get("/api/agents")
async def list_agents():
    return {"agents": chat_hub.agent_bus.list_agents()}


@app.post("/api/chat/{session_id}")
async def send_message(session_id: str, data: dict[str, Any]):
    session = chat_hub.get_session(session_id)
    if session is None:
        return {"error": "Session not found"}, 404

    content = data.get("content", "")
    events = await chat_hub.handle_user_message(session_id, content)
    return {
        "session": session.to_dict(),
        "events": events,
    }


@app.post("/api/agent/{session_id}")
async def call_agent(session_id: str, data: dict[str, Any]):
    session = chat_hub.get_session(session_id)
    if session is None:
        return {"error": "Session not found"}, 404

    agent_name = data.get("agent", "")
    content = data.get("content", "")
    events = await chat_hub.handle_agent_call(session_id, agent_name, content)
    return {
        "session": session.to_dict(),
        "events": events,
    }


@app.get("/api/session/{session_id}/story_props")
async def get_story_props(session_id: str):
    session = chat_hub.get_session(session_id)
    if session is None:
        return {"error": "Session not found"}, 404

    # First try in-memory cached props
    props = session.metadata.get("story_props")
    if props:
        return {"story_props": props, "cached": True}

    # Then try file path
    props_path = session.metadata.get("story_props_path")
    if props_path and Path(props_path).is_file():
        try:
            props = json.loads(Path(props_path).read_text(encoding="utf-8"))
            session.metadata["story_props"] = props
            return {"story_props": props, "path": props_path, "cached": False}
        except Exception as e:
            return {"error": f"Failed to read story_props: {e}"}, 500

    # Fall back to searching agent attachments for JSON
    for m in reversed(session.messages):
        for a in m.attachments:
            if a.type == "json" and "story_props" in a.label.lower():
                try:
                    props = json.loads(a.content)
                    session.metadata["story_props"] = props
                    return {"story_props": props, "source": "attachment", "cached": False}
                except Exception:
                    pass

    return {"error": "No story_props found for this session"}, 404


@app.post("/api/upload/{session_id}")
async def upload_character(session_id: str, file: UploadFile = File(...)):
    session = chat_hub.get_session(session_id)
    if session is None:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    if not file.content_type or not file.content_type.startswith("image/"):
        return JSONResponse({"error": "Only image files are allowed"}, status_code=400)

    assets_dir = chat_hub.sessions_dir / session_id / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "character.png").suffix or ".png"
    dest = assets_dir / f"character{ext}"
    content = await file.read()
    dest.write_bytes(content)

    session.metadata["character_path"] = str(dest.resolve())
    session.metadata["character_filename"] = file.filename

    # Analyze character image with GPT-4o vision
    character_description = ""
    try:
        from llm.vision_client import analyze_character_image, describe_character
        analysis = analyze_character_image(str(dest.resolve()))
        if analysis:
            session.metadata["character_analysis"] = analysis
            character_description = describe_character(analysis)
            session.metadata["character_description"] = character_description
    except Exception:
        pass

    msg = f"✅ عکس کاراکتر آپلود شد: `{file.filename}`\n"
    if character_description:
        msg += f"\n**تحلیل بصری:**\n{character_description}\n"
        msg += "\nاین تحلیل در اختیار همه ایجنت‌ها قرار گرفته است."
    else:
        msg += "این عکس در خروجی نهایی استفاده خواهد شد."

    session.add_system_message(msg, phase="character")
    chat_hub._save_session(session)
    return {
        "filename": file.filename,
        "path": str(dest),
        "character_description": character_description,
        "message": "Character image uploaded successfully",
        "session": session.to_dict(),
    }


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    await ws.accept()
    session = chat_hub.get_session(session_id)
    if session is None:
        session = chat_hub.create_session()
        await ws.send_json({"type": "session_created", "session_id": session.id})
    else:
        await ws.send_json({"type": "session_loaded", "session": session.to_dict()})

    def send_event(event: dict[str, Any]):
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(ws.send_json(event))
            loop.close()
        except Exception:
            pass

    chat_hub.connect_ws(session_id, send_event)

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type", "")

            if msg_type == "user_message":
                events = await chat_hub.handle_user_message(
                    session_id, data.get("content", "")
                )
                for event in events:
                    await ws.send_json(event)
                session = chat_hub.get_session(session_id)
                if session:
                    await ws.send_json({
                        "type": "session_update",
                        "session": session.to_dict() if session else None,
                    })

            elif msg_type == "call_agent":
                events = await chat_hub.handle_agent_call(
                    session_id,
                    data.get("agent", ""),
                    data.get("content", ""),
                )
                for event in events:
                    await ws.send_json(event)

            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})

    except WebSocketDisconnect:
        chat_hub.disconnect_ws(session_id, send_event)
    except Exception as e:
        chat_hub.disconnect_ws(session_id, send_event)
        try:
            await ws.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
