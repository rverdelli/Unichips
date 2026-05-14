"""
FastAPI backend — pagina pubblica + API chatbot + dashboard admin.
"""
import sqlite3
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel

from modules.database import (
    init_db, get_complaints, get_complaint_by_id,
    update_complaint, save_complaint,
    get_chatbot_config, save_chatbot_config, get_stats, DB_PATH,
)
from modules.chatbot import init_state, process_message
from modules import llm as llm_module
from modules.constants import COMPLAINT_UPDATABLE_COLUMNS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="San Carlo CarloBot Demo")
init_db()

# ── Chat session store ────────────────────────────────────────────────────────
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

class PrefillRequest(BaseModel):
    session_id: str
    name: str = ""
    email: str = ""

class ComplaintUpdate(BaseModel):
    status: str | None = None
    ai_response: str | None = None
    closed_at: str | None = None
    priority: str | None = None

class ConfigPayload(BaseModel):
    common_knowledge: str = ""
    classification_rules: str = ""
    anthropic_api_key: str = ""
    model: str = "claude-haiku-4-5-20251001"


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC CHAT API
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        state = get_session(req.session_id)
        reply, new_state, suggestions = process_message(req.message, state, req.history)
        set_session(req.session_id, new_state)
        collected = new_state.get("collected", {})
        return {
            "reply": reply,
            "suggestions": suggestions,
            "phase": new_state.get("phase"),
            "show_upload": new_state.get("phase") == "collecting",
            "complaint_id": new_state.get("complaint_id"),
            "customer_name":  collected.get("name")  if new_state.get("phase") == "done" else None,
            "customer_email": collected.get("email") if new_state.get("phase") == "done" else None,
        }
    except Exception as e:
        logger.error("Chat error: %s", e, exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Errore interno. Riprova."})


@app.post("/api/session/reset")
async def reset_session(req: ResetRequest):
    set_session(req.session_id, init_state())
    return {"ok": True}


@app.post("/api/session/prefill")
async def prefill_session(req: PrefillRequest):
    state = get_session(req.session_id)
    collected = state.get("collected", {})
    if req.name:  collected["name"]  = req.name
    if req.email: collected["email"] = req.email
    state["collected"] = collected
    set_session(req.session_id, state)
    return {"ok": True}


@app.get("/api/status")
async def status():
    config = get_chatbot_config()
    return {
        "llm_configured": llm_module.is_configured(config),
        "active_sessions": len(_sessions),
    }


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN API
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/admin/api/complaints")
async def admin_list_complaints(
    status: str = Query("", alias="status"),
    category: str = Query("", alias="category"),
    search: str = Query("", alias="search"),
    limit: int = 100,
    offset: int = 0,
):
    filters = {}
    if status:   filters["status"]   = status
    if category: filters["category"] = category
    if search:   filters["search"]   = search
    rows = get_complaints(filters)
    total = len(rows)
    return {"total": total, "items": rows[offset: offset + limit]}


@app.get("/admin/api/complaints/{complaint_id}")
async def admin_get_complaint(complaint_id: int):
    row = get_complaint_by_id(complaint_id)
    if not row:
        return JSONResponse(status_code=404, content={"error": "Non trovato"})
    return row


@app.patch("/admin/api/complaints/{complaint_id}")
async def admin_update_complaint(complaint_id: int, payload: ComplaintUpdate):
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not data:
        return {"ok": True}
    # auto-set closed_at when closing
    if data.get("status") in ("Chiuso", "Chiuso automaticamente") and "closed_at" not in data:
        data["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update_complaint(complaint_id, data)
    return {"ok": True}


@app.get("/admin/api/stats")
async def admin_stats(
    date_from: str = Query("", alias="date_from"),
    date_to:   str = Query("", alias="date_to"),
    product:   str = Query("", alias="product"),
    category:  str = Query("", alias="category"),
):
    rows = get_stats()

    # Parse and filter
    def parse_dt(s):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try: return datetime.strptime(s, fmt)
            except: pass
        return None

    if date_from:
        df = parse_dt(date_from)
        if df: rows = [r for r in rows if parse_dt(r.get("created_at","") or "") and parse_dt(r["created_at"]) >= df]
    if date_to:
        dt = parse_dt(date_to + " 23:59:59")
        if dt: rows = [r for r in rows if parse_dt(r.get("created_at","") or "") and parse_dt(r["created_at"]) <= dt]
    if product:  rows = [r for r in rows if r.get("product")           == product]
    if category: rows = [r for r in rows if r.get("problem_category")  == category]

    total   = len(rows)
    open_c  = sum(1 for r in rows if r.get("status") == "Aperto")
    auto_c  = sum(1 for r in rows if r.get("status") == "Chiuso automaticamente")
    pending = sum(1 for r in rows if r.get("status") in ("Aperto", "In lavorazione"))

    # Avg closure days
    closed = [r for r in rows if r.get("closed_at")]
    avg_days = None
    if closed:
        deltas = []
        for r in closed:
            c = parse_dt(r["created_at"])
            cl = parse_dt(r["closed_at"])
            if c and cl: deltas.append((cl - c).days)
        avg_days = round(sum(deltas) / len(deltas), 1) if deltas else None

    top_cat = None
    if rows:
        from collections import Counter
        counts = Counter(r.get("problem_category","") for r in rows if r.get("problem_category"))
        top_cat = counts.most_common(1)[0][0] if counts else None

    # Monthly trend (last 24 months)
    from collections import defaultdict
    monthly = defaultdict(int)
    for r in rows:
        dt = parse_dt(r.get("created_at","") or "")
        if dt:
            key = dt.strftime("%Y-%m")
            monthly[key] += 1
    # Fill missing months
    now = datetime.now()
    all_months = [(now - timedelta(days=30*i)).strftime("%Y-%m") for i in range(23,-1,-1)]
    monthly_series = [{"month": m, "count": monthly.get(m, 0)} for m in all_months]

    # By category
    cat_counts = defaultdict(int)
    for r in rows:
        cat_counts[r.get("problem_category","Altro")] += 1
    by_category = [{"label": k, "value": v} for k, v in sorted(cat_counts.items(), key=lambda x: -x[1])]

    # By product
    prod_counts = defaultdict(int)
    for r in rows:
        prod_counts[r.get("product","—")] += 1
    by_product = [{"label": k, "value": v} for k, v in sorted(prod_counts.items(), key=lambda x: -x[1])[:10]]

    # Auto vs manual
    auto_count   = sum(1 for r in rows if r.get("classification") == "semplice")
    manual_count = sum(1 for r in rows if r.get("classification") == "complesso")
    auto_vs_manual = [
        {"label": "Risposta automatica", "value": auto_count},
        {"label": "Gestito dal team",    "value": manual_count},
    ]

    # Avg days to close by category
    cat_days = defaultdict(list)
    for r in closed:
        cat = r.get("problem_category","Altro")
        c  = parse_dt(r["created_at"])
        cl = parse_dt(r["closed_at"])
        if c and cl: cat_days[cat].append((cl - c).days)
    avg_by_cat = [
        {"label": k, "value": round(sum(v)/len(v), 1)}
        for k, v in sorted(cat_days.items(), key=lambda x: -sum(x[1])/len(x[1]))
        if v
    ]

    # Top 5 products
    top5 = sorted(prod_counts.items(), key=lambda x: -x[1])[:5]

    return {
        "kpis": {
            "total":    total,
            "open":     open_c,
            "auto":     auto_c,
            "pending":  pending,
            "avg_days": avg_days,
            "top_cat":  top_cat,
        },
        "monthly":        monthly_series,
        "by_category":    by_category,
        "by_product":     by_product,
        "auto_vs_manual": auto_vs_manual,
        "avg_by_cat":     avg_by_cat,
        "top5_products":  [{"product": k, "count": v} for k, v in top5],
        "unique_products": sorted(set(r.get("product","") for r in get_stats() if r.get("product"))),
        "unique_categories": sorted(set(r.get("problem_category","") for r in get_stats() if r.get("problem_category"))),
    }


@app.get("/admin/api/config")
async def admin_get_config():
    return get_chatbot_config()


@app.post("/admin/api/config")
async def admin_save_config(payload: ConfigPayload):
    import os
    cfg = payload.model_dump()
    save_chatbot_config(cfg)
    if cfg.get("anthropic_api_key"):
        os.environ["ANTHROPIC_API_KEY"] = cfg["anthropic_api_key"]
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════════
# STATIC & HTML
# ══════════════════════════════════════════════════════════════════════════════
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse("templates/index.html")

@app.get("/admin", response_class=HTMLResponse)
async def admin():
    return FileResponse("templates/admin.html")
