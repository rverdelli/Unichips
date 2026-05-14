"""
FastAPI backend — serve la pagina pubblica e le API del chatbot.
La logica del chatbot rimane in modules/ invariata.
"""
import threading
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel

from modules.database import init_db
from modules.chatbot import init_state, process_message
from modules import llm as llm_module
from modules.database import get_chatbot_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="San Carlo CarloBot Demo")
init_db()

# ── In-memory session store (demo) ───────────────────────────────────────────
_sessions: dict[str, dict] = {}
_lock = threading.Lock()

def get_session(session_id: str) -> dict:
    with _lock:
        if session_id not in _sessions:
            _sessions[session_id] = init_state()
        return dict(_sessions[session_id])

def set_session(session_id: str, state: dict):
    with _lock:
        _sessions[session_id] = state


# ── Pydantic models ───────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: list[dict] = []

class ResetRequest(BaseModel):
    session_id: str


# ── API endpoints ─────────────────────────────────────────────────────────────
@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        state = get_session(req.session_id)
        reply, new_state, suggestions = process_message(req.message, state, req.history)
        set_session(req.session_id, new_state)
        return {
            "reply": reply,
            "suggestions": suggestions,
            "phase": new_state.get("phase"),
            "show_upload": new_state.get("phase") == "collecting",
            "complaint_id": new_state.get("complaint_id"),
        }
    except Exception as e:
        logger.error("Chat error: %s", e, exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Errore interno. Riprova."})


@app.post("/api/session/reset")
async def reset_session(req: ResetRequest):
    set_session(req.session_id, init_state())
    return {"ok": True}


@app.get("/api/status")
async def status():
    config = get_chatbot_config()
    return {
        "llm_configured": llm_module.is_configured(config),
        "active_sessions": len(_sessions),
    }


# ── Static files & HTML ───────────────────────────────────────────────────────
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse("templates/index.html")
