import sqlite3
import json
import logging
from pathlib import Path

from modules.constants import COMPLAINT_UPDATABLE_COLUMNS, DEFAULT_CLUSTERS, PRODUCTS

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "complaints.db"
CONFIG_PATH = Path(__file__).parent.parent / "data" / "chatbot_config.json"
UPLOAD_ROOT = Path(__file__).parent.parent / "data" / "uploads"

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


def _migrate_db(conn):
    """Add new columns to existing DB without recreating it."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(complaints)").fetchall()}
    added = False
    for col, definition in [
        ("cluster1", "TEXT DEFAULT ''"),
        ("cluster2", "TEXT DEFAULT ''"),
        ("gravity",  "TEXT DEFAULT ''"),
        ("conversation_history", "TEXT DEFAULT ''"),
    ]:
        if col not in existing:
            conn.execute(f"ALTER TABLE complaints ADD COLUMN {col} {definition}")
            added = True
    if "gravity" not in existing and "priority" in existing:
        conn.execute("UPDATE complaints SET gravity = priority WHERE gravity IS NULL OR gravity = ''")
    if added:
        conn.commit()
    # Backfill cluster1/cluster2 for rows that have none yet
    _backfill_clusters(conn)


_CATEGORY_TO_CLUSTER = {
    "Patatina bruciata":     ("ORGANOLETTICO",        "DIFETTI VISIVI"),
    "Patatina verde":        ("ORGANOLETTICO",        "DIFETTI VISIVI"),
    "Prodotto sbriciolato":  ("DIFETTI DI PACKAGING", "ROTTURE/INTRINSECHE DI PRODOTTO"),
    "Gusto anomalo":         ("ORGANOLETTICO",        "GUSTO ANOMALO"),
    "Corpo estraneo":        ("CORPO ESTRANEO",       "VARI"),
    "Confezione vuota":      ("DIFETTI DI PACKAGING", "CARTONI VUOTI"),
    "Confezione danneggiata":("DIFETTI DI PACKAGING", "SALDATURE APERTE"),
    "Odore anomalo":         ("ORGANOLETTICO",        "CATTIVO SAPORE / ODORE / CONSISTENZA DA PACK-GADGET"),
    "Muffa / alterazione":   ("MICROBIOLOGICO",       "MUFFA"),
    "Altro":                 ("ORGANOLETTICO",        "GUSTO NON GRADITO"),
}

_COMPLAINT_LIST_COLUMNS = """
    id, created_at, customer_name, customer_email, product,
    problem_category, description, lot_code, expiry_date,
    purchase_location, status, priority, channel, classification,
    auto_response, ai_response, closed_at, has_photo, cluster1,
    cluster2, gravity
"""


def _backfill_clusters(conn):
    """Populate cluster1/cluster2 for rows that have none (existing mock data)."""
    rows = conn.execute(
        "SELECT id, problem_category FROM complaints WHERE cluster1 IS NULL OR cluster1 = ''"
    ).fetchall()
    if not rows:
        return
    updates = []
    for row in rows:
        cat = row[1] or "Altro"
        c1, c2 = _CATEGORY_TO_CLUSTER.get(cat, ("ORGANOLETTICO", "GUSTO NON GRADITO"))
        updates.append((c1, c2, row[0]))
    conn.executemany(
        "UPDATE complaints SET cluster1 = ?, cluster2 = ? WHERE id = ?", updates
    )
    conn.commit()


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
            priority TEXT DEFAULT 'Media',
            channel TEXT DEFAULT 'chatbot',
            classification TEXT,
            auto_response INTEGER DEFAULT 0,
            ai_response TEXT,
            closed_at TEXT,
            has_photo INTEGER DEFAULT 0,
            cluster1 TEXT DEFAULT '',
            cluster2 TEXT DEFAULT '',
            gravity TEXT DEFAULT '',
            conversation_history TEXT DEFAULT ''
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_status   ON complaints(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON complaints(problem_category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created  ON complaints(created_at)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS complaint_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER,
            session_id TEXT,
            original_filename TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            content_type TEXT DEFAULT '',
            size_bytes INTEGER DEFAULT 0,
            uploaded_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attachment_complaint ON complaint_attachments(complaint_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attachment_session ON complaint_attachments(session_id)")
    conn.commit()
    _migrate_db(conn)
    # Index on cluster1 only after migration ensures the column exists
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cluster1 ON complaints(cluster1)")
    conn.commit()
    conn.close()


def _serialize_conversation_history(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return json.dumps(str(value), ensure_ascii=False)


def save_complaint(data):
    gravity = data.get("gravity") or data.get("priority") or "Media"
    conn = get_connection()
    cursor = conn.execute("""
        INSERT INTO complaints
        (customer_name, customer_email, product, problem_category, description,
         lot_code, expiry_date, purchase_location, status, priority, channel,
         classification, auto_response, ai_response, has_photo, cluster1, cluster2,
         gravity, conversation_history)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data.get("name"), data.get("email"), data.get("product"),
        data.get("problem_category"), data.get("description"),
        data.get("lot_code", ""), data.get("expiry_date", ""),
        data.get("purchase_location", ""), data.get("status", "Aperto"),
        gravity, data.get("channel", "chatbot"),
        data.get("classification"), 1 if data.get("auto_response") else 0,
        data.get("ai_response", ""), 1 if data.get("has_photo") else 0,
        data.get("cluster1", ""), data.get("cluster2", ""), gravity,
        _serialize_conversation_history(data.get("conversation_history")),
    ))
    complaint_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return complaint_id


def get_complaints(filters=None):
    conn = get_connection()
    query = f"SELECT {_COMPLAINT_LIST_COLUMNS} FROM complaints WHERE 1=1"
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
    invalid = set(data.keys()) - COMPLAINT_UPDATABLE_COLUMNS
    if invalid:
        raise ValueError(f"Attempted to update non-whitelisted columns: {invalid}")
    conn = get_connection()
    set_clauses = [f"{k} = ?" for k in data]
    params = list(data.values()) + [complaint_id]
    conn.execute(f"UPDATE complaints SET {', '.join(set_clauses)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def save_attachment_record(
    *,
    session_id: str | None,
    complaint_id: int | None,
    original_filename: str,
    stored_path: str,
    content_type: str,
    size_bytes: int,
) -> int:
    conn = get_connection()
    cursor = conn.execute("""
        INSERT INTO complaint_attachments
        (session_id, complaint_id, original_filename, stored_path, content_type, size_bytes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session_id, complaint_id, original_filename, stored_path, content_type, size_bytes))
    attachment_id = cursor.lastrowid
    if complaint_id:
        conn.execute("UPDATE complaints SET has_photo = 1 WHERE id = ?", (complaint_id,))
    conn.commit()
    conn.close()
    return attachment_id


def get_pending_attachments(session_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM complaint_attachments
        WHERE session_id = ? AND complaint_id IS NULL
        ORDER BY uploaded_at ASC, id ASC
    """, (session_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def attach_pending_attachment(attachment_id: int, complaint_id: int, stored_path: str):
    conn = get_connection()
    conn.execute("""
        UPDATE complaint_attachments
        SET complaint_id = ?, stored_path = ?
        WHERE id = ?
    """, (complaint_id, stored_path, attachment_id))
    conn.execute("UPDATE complaints SET has_photo = 1 WHERE id = ?", (complaint_id,))
    conn.commit()
    conn.close()


def get_complaint_attachments(complaint_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM complaint_attachments
        WHERE complaint_id = ?
        ORDER BY uploaded_at ASC, id ASC
    """, (complaint_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_attachment_by_id(attachment_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM complaint_attachments WHERE id = ?",
        (attachment_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_chatbot_config():
    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if "clusters" not in cfg:
            cfg["clusters"] = DEFAULT_CLUSTERS
        if "products" not in cfg:
            cfg["products"] = PRODUCTS
        return cfg
    return {
        "common_knowledge": DEFAULT_COMMON_KNOWLEDGE,
        "classification_rules": DEFAULT_CLASSIFICATION_RULES,
        "clusters": DEFAULT_CLUSTERS,
        "products": PRODUCTS,
    }


def save_chatbot_config(config):
    if not config.get("clusters"):
        config["clusters"] = DEFAULT_CLUSTERS
    products = config.get("products") or PRODUCTS
    clean_products = []
    seen = set()
    for product in products:
        value = str(product).strip()
        key = value.lower()
        if value and key not in seen:
            clean_products.append(value)
            seen.add(key)
    config["products"] = clean_products or PRODUCTS
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_stats():
    conn = get_connection()
    rows = conn.execute(f"SELECT {_COMPLAINT_LIST_COLUMNS} FROM complaints").fetchall()
    conn.close()
    return [dict(r) for r in rows]
