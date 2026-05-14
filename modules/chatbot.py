"""
Chatbot conversation logic (state machine).
LLM calls are delegated to modules/llm.py — swap API key to go live.
"""
import re
from modules.database import save_complaint, get_chatbot_config

REQUIRED_FIELDS = ["name", "email", "product", "problem_category", "lot_code", "description"]

FIELD_LABELS = {
    "name": "Nome e cognome",
    "email": "Email di contatto",
    "product": "Prodotto acquistato",
    "problem_category": "Tipo di problema",
    "lot_code": "Codice lotto",
    "description": "Descrizione dell'accaduto",
}

FIELD_PROMPTS = {
    "name": "Puoi dirmi il tuo **nome e cognome**?",
    "email": "Qual è il tuo **indirizzo email** di contatto?",
    "product": "Qual è il **prodotto** che hai acquistato? (es. Più Gusto Classica, Veggy Good, ecc.)",
    "problem_category": "Che tipo di **problema** hai riscontrato?",
    "lot_code": (
        "Hai il **codice lotto**? Lo trovi sul retro o sul bordo della confezione, "
        "vicino alla data di scadenza. È una sequenza alfanumerica tipo: L23A45B."
    ),
    "description": "Puoi descrivermi brevemente **cosa è successo**?",
}

PRODUCTS = [
    "Più Gusto Vivace", "Più Gusto Lime e Pepe Rosa", "Più Gusto Porchetta",
    "Più Gusto Tartufo", "Classica", "Rustica", "Veggy Good",
    "Pop Corn San Carlo", "Wacko's", "Highlander",
]

CATEGORIES = [
    "Patatina bruciata", "Patatina verde", "Prodotto sbriciolato",
    "Gusto anomalo", "Corpo estraneo", "Confezione vuota",
    "Confezione danneggiata", "Odore anomalo", "Muffa / alterazione", "Altro",
]


# ── State helpers ────────────────────────────────────────────────────────────

def init_state():
    return {
        "phase": "welcome",
        "collected": {},
        "messages": [],
        "complaint_id": None,
        "waiting_for": None,
    }


def get_missing_fields(collected):
    return [f for f in REQUIRED_FIELDS if not collected.get(f)]


def build_summary(collected):
    lines = []
    for field in REQUIRED_FIELDS:
        val = collected.get(field)
        if val:
            lines.append(f"- **{FIELD_LABELS[field]}**: {val}")
    return "\n".join(lines)


# ── Fallback: regex-based extraction (used when API unavailable) ─────────────

def _extract_fields_regex(text: str, collected: dict) -> dict:
    updated = dict(collected)

    email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
    if email_match and not updated.get("email"):
        updated["email"] = email_match.group(0)

    # Lot code: must contain at least one digit (avoids matching common words like "lotto")
    lot_match = re.search(r"\b[Ll]\d[0-9A-Za-z]{3,10}\b|\b\d{2}[A-Za-z]\d{2,8}\b", text)
    if lot_match and not updated.get("lot_code"):
        updated["lot_code"] = lot_match.group(0).upper()

    if not updated.get("product"):
        text_lower = text.lower()
        for p in PRODUCTS:
            if p.lower() in text_lower:
                updated["product"] = p
                break

    if not updated.get("problem_category"):
        text_lower = text.lower()
        cat_keywords = {
            "Patatina bruciata": ["bruciata", "bruciato", "nera", "scura"],
            "Patatina verde": ["verde", "verdi"],
            "Prodotto sbriciolato": ["sbriciolata", "rotta", "frantumata"],
            "Gusto anomalo": ["gusto strano", "sapore strano"],
            "Corpo estraneo": ["corpo estraneo", "capello", "insetto", "plastica", "metallo"],
            "Confezione vuota": ["vuota", "vuoto"],
            "Confezione danneggiata": ["danneggiata", "busta rotta"],
            "Odore anomalo": ["odore", "puzza"],
            "Muffa / alterazione": ["muffa", "ammuffita"],
        }
        for cat, kws in cat_keywords.items():
            if any(kw in text_lower for kw in kws):
                updated["problem_category"] = cat
                break

    return updated


# ── Fallback: deterministic reply (used when API unavailable) ────────────────

def _deterministic_reply(user_text: str, state: dict) -> tuple:
    text_lower = user_text.lower()
    if "reclamo" in text_lower or "segnalazione" in text_lower or "problema" in text_lower:
        return (
            "Mi dispiace per l'inconveniente. Posso aiutarti ad aprire una segnalazione. "
            "Puoi dirmi il tuo **nome e cognome**?",
            ["Voglio aprire un reclamo"],
        )
    if "lotto" in text_lower:
        return (
            "Il **codice lotto** si trova sul retro o sul bordo della confezione, "
            "vicino alla data di scadenza. È una sequenza come `L23A45B`.",
            ["Voglio sottoporre un reclamo", "Avete prodotti senza glutine?"],
        )
    if "glutine" in text_lower:
        return (
            "Alcuni prodotti come la linea Veggy Good sono disponibili senza glutine. "
            "Verifica sempre l'etichetta del prodotto acquistato.",
            ["Voglio sottoporre un reclamo", "Dove trovo il lotto sulla confezione?"],
        )
    return (
        "Ciao! Sono qui per aiutarti. Puoi chiedermi informazioni sui prodotti "
        "o aprire una segnalazione.",
        ["Voglio sottoporre un reclamo", "Dove trovo il lotto sulla confezione?", "Avete prodotti senza glutine?"],
    )


# ── Main entry point ─────────────────────────────────────────────────────────

def process_message(user_text: str, state: dict, conversation_history: list = None):
    """
    Main chatbot logic. Returns (bot_reply, updated_state, suggestions).
    Uses LLM when configured, falls back to deterministic logic otherwise.
    """
    from modules import llm

    config = get_chatbot_config()
    phase = state.get("phase", "welcome")
    collected = state.get("collected", {})
    suggestions = []

    # ── WELCOME ──────────────────────────────────────────────────────────────
    if phase == "welcome":
        text_lower = user_text.lower()

        # Detect complaint intent to transition phase immediately
        complaint_intent = any(w in text_lower for w in [
            "reclamo", "segnalazione", "problema", "rotto", "bruciata",
            "corpo estraneo", "vuota", "muffa", "odore", "segnalare",
        ])

        if complaint_intent:
            state["phase"] = "collecting"
            state["waiting_for"] = "name"
            reply = (
                "Mi dispiace per l'inconveniente. Per gestire correttamente la tua segnalazione "
                "ho bisogno di alcune informazioni:\n\n"
                "- Nome e cognome\n"
                "- Email di contatto\n"
                "- Prodotto acquistato\n"
                "- Tipo di problema riscontrato\n"
                "- Codice lotto\n"
                "- Data di scadenza *(se disponibile)*\n"
                "- Luogo di acquisto *(se disponibile)*\n"
                "- Foto della confezione *(opzionale)*\n"
                "- Breve descrizione dell'accaduto\n\n"
                "Puoi fornirmi tutte le informazioni insieme oppure una alla volta. "
                "Iniziamo: puoi dirmi il tuo **nome e cognome**?"
            )
            return reply, state, []

        # For generic questions use LLM if available, else fallback
        if llm.is_configured(config):
            hist = conversation_history or []
            reply, suggestions = llm.generate_chat_reply(user_text, hist, state, config)
        else:
            reply, suggestions = _deterministic_reply(user_text, state)

        return reply, state, suggestions

    # ── COLLECTING ───────────────────────────────────────────────────────────
    if phase == "collecting":
        # Extract fields from user message
        if llm.is_configured(config):
            collected = llm.extract_complaint_fields(user_text, collected, config)
        else:
            collected = _extract_fields_regex(user_text, collected)

        # If we were waiting for a specific field and it's still empty, assign raw text
        wf = state.get("waiting_for")
        if wf and not collected.get(wf):
            collected[wf] = user_text.strip()

        state["collected"] = collected
        missing = get_missing_fields(collected)

        if not missing:
            # All mandatory fields collected — classify and save
            from modules.classifier import classify_complaint
            result = classify_complaint(collected, config)
            complaint_data = {**collected, **result, "channel": "chatbot"}
            complaint_id = save_complaint(complaint_data)
            state["complaint_id"] = complaint_id
            state["phase"] = "done"
            state["classification"] = result["classification"]

            summary = build_summary(collected)

            if result["classification"] == "semplice":
                reply = (
                    f"✅ **Segnalazione #{complaint_id} registrata.**\n\n"
                    f"Riepilogo informazioni ricevute:\n{summary}\n\n"
                    "---\n"
                    + result.get("ai_response", (
                        "La tua segnalazione è stata registrata e sarà utilizzata "
                        "per monitorare la qualità dei nostri prodotti."
                    ))
                    + "\n\nRiceverai una email di conferma all'indirizzo indicato."
                )
            else:
                reply = (
                    f"✅ **Segnalazione #{complaint_id} registrata.**\n\n"
                    f"Riepilogo informazioni ricevute:\n{summary}\n\n"
                    "---\n"
                    + result.get("ai_response", (
                        "Il reclamo sarà preso in carico dal nostro team qualità. "
                        "Riceverai un aggiornamento via email entro 2-3 giorni lavorativi."
                    ))
                )
            suggestions = ["Grazie!", "Aprire un altro reclamo"]

        else:
            next_field = missing[0]
            state["waiting_for"] = next_field
            already = [f for f in REQUIRED_FIELDS if collected.get(f)]
            if already:
                summary = build_summary(collected)
                reply = (
                    f"Grazie! Ho già raccolto:\n{summary}\n\n"
                    f"Mi manca ancora: {FIELD_PROMPTS[next_field]}"
                )
            else:
                reply = FIELD_PROMPTS[next_field]

        return reply, state, suggestions

    # ── DONE ─────────────────────────────────────────────────────────────────
    if phase == "done":
        text_lower = user_text.lower()
        if "altro" in text_lower or "nuovo" in text_lower or "aprire" in text_lower:
            new_state = init_state()
            new_state["phase"] = "collecting"
            new_state["waiting_for"] = "name"
            return "Certo! Apriamo una nuova segnalazione. Puoi dirmi il tuo **nome e cognome**?", new_state, []
        return (
            "Grazie per aver contattato San Carlo! "
            "Se hai bisogno di altro non esitare a scrivermi. 😊",
            state,
            ["Aprire un altro reclamo"],
        )

    return "Come posso aiutarti?", state, []
