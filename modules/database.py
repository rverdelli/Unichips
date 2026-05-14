import sqlite3
import json
import logging
from pathlib import Path

from modules.constants import COMPLAINT_UPDATABLE_COLUMNS

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "complaints.db"
CONFIG_PATH = Path(__file__).parent.parent / "data" / "chatbot_config.json"

DEFAULT_COMMON_KNOWLEDGE = """- Il codice lotto è normalmente indicato sul retro o sul bordo della confezione, vicino alla data di scadenza.
- Le patatine possono presentare leggere differenze di colore, forma e croccantezza perché derivano da materie prime naturali.
- Alcuni prodotti possono avere informazioni specifiche su allergeni e ingredienti riportate in etichetta.
- Per informazioni su allergeni, ingredienti o idoneità alimentari, il consumatore deve sempre fare riferimento all'etichetta del prodotto acquistato.
- Le segnalazioni con corpo estraneo, confezione vuota, odore anomalo o possibile contaminazione devono essere inoltrate al team qualità."""

DEFAULT_CLASSIFICATION_RULES = """- Reclami SEMPLICI (risposta automatica, chiusura immediata): patatina bruciata/scura, patatina verde, prodotto sbriciolato, lievi variazioni di colore o forma, confezione danneggiata, gusto lievemente anomalo. Per questi casi spiega cordialmente la causa naturale o logistica del problema, conferma che la segnalazione è registrata e verrà usata per migliorare i processi. Nessun rimborso né buono.
- Reclami COMPLESSI (escalation al team qualità): corpo estraneo, confezione vuota o quasi vuota, muffa, odore anomalo, sapore fortemente alterato, possibile contaminazione, problemi di sicurezza alimentare. Per questi casi esprimi dispiacere, offri rimborso completo del prodotto + buono acquisto da €5, chiedi di conservare la confezione con codice lotto visibile, e comunica che il team la contatterà entro 24 ore lavorative.
- Non fornire mai spiegazioni definitive su possibili contaminazioni o corpi estranei — quelle competono al team qualità.
- Tono sempre cordiale ed empatico: il cliente deve sentirsi ascoltato."""


def get_connection():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT (datetime('now')),
            customer_name TEXT,
            customer_email TEXT,
            product TEXT,
            problem_category TEXT,
            description TEXT,
            lot_code TEXT,
            expiry_date TEXT,
            purchase_location TEXT,
            status TEXT DEFAULT 'Aperto',
            priority TEXT DEFAULT 'Normale',
            channel TEXT DEFAULT 'chatbot',
            classification TEXT,
            auto_response INTEGER DEFAULT 0,
            ai_response TEXT,
            closed_at TEXT,
            has_photo INTEGER DEFAULT 0
        )
    """)
    # Indexes on columns used in filters and analytics
    conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON complaints(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON complaints(problem_category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON complaints(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_channel ON complaints(channel)")
    conn.commit()
    conn.close()


def save_complaint(data):
    conn = get_connection()
    cursor = conn.execute("""
        INSERT INTO complaints
        (customer_name, customer_email, product, problem_category, description,
         lot_code, expiry_date, purchase_location, status, priority, channel,
         classification, auto_response, ai_response, has_photo)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data.get("name"), data.get("email"), data.get("product"),
        data.get("problem_category"), data.get("description"),
        data.get("lot_code", ""), data.get("expiry_date", ""),
        data.get("purchase_location", ""), data.get("status", "Aperto"),
        data.get("priority", "Normale"), data.get("channel", "chatbot"),
        data.get("classification"), 1 if data.get("auto_response") else 0,
        data.get("ai_response", ""), 1 if data.get("has_photo") else 0,
    ))
    complaint_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return complaint_id


def get_complaints(filters=None):
    conn = get_connection()
    query = "SELECT * FROM complaints WHERE 1=1"
    params = []
    if filters:
        if filters.get("status") and filters["status"] != "Tutti":
            query += " AND status = ?"
            params.append(filters["status"])
        if filters.get("category") and filters["category"] != "Tutte":
            query += " AND problem_category = ?"
            params.append(filters["category"])
        if filters.get("search"):
            s = f"%{filters['search']}%"
            query += " AND (customer_name LIKE ? OR product LIKE ? OR description LIKE ?)"
            params.extend([s, s, s])
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_complaint_by_id(complaint_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_complaint(complaint_id, data):
    # Whitelist columns to prevent injection via dynamic key construction
    invalid = set(data.keys()) - COMPLAINT_UPDATABLE_COLUMNS
    if invalid:
        raise ValueError(f"Attempted to update non-whitelisted columns: {invalid}")
    conn = get_connection()
    set_clauses = [f"{k} = ?" for k in data]
    params = list(data.values()) + [complaint_id]
    conn.execute(f"UPDATE complaints SET {', '.join(set_clauses)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def get_chatbot_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {
        "common_knowledge": DEFAULT_COMMON_KNOWLEDGE,
        "classification_rules": DEFAULT_CLASSIFICATION_RULES,
    }


def save_chatbot_config(config):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_stats():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM complaints").fetchall()
    conn.close()
    return [dict(r) for r in rows]
