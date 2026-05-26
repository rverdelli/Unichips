"""
Chatbot conversation logic (state machine).
LLM calls are delegated to modules/llm.py — swap API key to go live.
"""
import logging
import re

from modules.database import save_complaint, get_chatbot_config
from modules.constants import (
    REQUIRED_COMPLAINT_FIELDS, FIELD_LABELS, FIELD_PROMPTS,
    PRODUCTS, CATEGORIES, COMPLAINT_INTENT_KEYWORDS,
)

logger = logging.getLogger(__name__)

MAX_FIELD_LENGTH = 1000  # Guard against absurdly long inputs


# ── State helpers ────────────────────────────────────────────────────────────

def init_state() -> dict:
    return {
        "phase": "welcome",
        "collected": {},
        "complaint_id": None,
        "waiting_for": None,
    }


def get_missing_fields(collected: dict) -> list[str]:
    return [f for f in REQUIRED_COMPLAINT_FIELDS if not collected.get(f)]


def build_summary(collected: dict) -> str:
    lines = []
    for field in REQUIRED_COMPLAINT_FIELDS:
        val = collected.get(field)
        if val:
            lines.append(f"- **{FIELD_LABELS[field]}**: {val}")
    return "\n".join(lines)


LOT_CODE_RE = re.compile(r'\bLT\d{5}\b', re.IGNORECASE)
LOT_CODE_HINT = (
    "Il codice lotto deve essere nel formato **LT seguito da 5 cifre** "
    "(es. `LT12345`). Lo trovi sul retro o sul bordo della confezione, "
    "vicino alla data di scadenza. Puoi riprovare?"
)


# ── Fallback: regex-based extraction (used when API unavailable) ─────────────

def _extract_fields_regex(text: str, collected: dict) -> dict:
    updated = dict(collected)

    email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.[a-zA-Z]{2,}", text)
    if email_match and not updated.get("email"):
        updated["email"] = email_match.group(0)

    lot_match = LOT_CODE_RE.search(text)
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


_CAT_KEYWORDS = {
    "Patatina bruciata":    ["bruciata", "bruciate", "nera", "scura", "carbonizzata"],
    "Patatina verde":       ["verde", "verdi", "inverdimento"],
    "Prodotto sbriciolato": ["sbriciolata", "sbriciolate", "rotta", "rotte", "frantumata", "in polvere"],
    "Gusto anomalo":        ["gusto strano", "sapore strano", "retrogusto", "amaro", "metallico"],
    "Corpo estraneo":       ["corpo estraneo", "capello", "insetto", "mosca", "plastica", "metallo", "vetro", "frammento"],
    "Confezione vuota":     ["vuota", "vuoto", "confezione vuota"],
    "Confezione danneggiata": ["danneggiata", "danneggiato", "aperta", "strappata", "busta rotta"],
    "Odore anomalo":        ["odore", "puzza", "rancido", "sgradevole"],
    "Muffa / alterazione":  ["muffa", "ammuffita", "alterazione", "chiazze bianche"],
}

def _infer_category(description: str) -> str:
    text = description.lower()
    for cat, kws in _CAT_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return cat
    return "Altro"


# ── Fallback: deterministic reply (used when API unavailable) ────────────────

def _deterministic_reply(user_text: str, state: dict) -> tuple[str, list]:
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

def process_message(
    user_text: str,
    state: dict,
    conversation_history: list | None = None,
) -> tuple[str, dict, list]:
    """
    Main chatbot logic. Returns (bot_reply, updated_state, suggestions).
    Uses LLM when configured, falls back to deterministic logic otherwise.
    """
    from modules import llm

    config = get_chatbot_config()
    phase = state.get("phase", "welcome")
    collected = state.get("collected", {})
    suggestions: list[str] = []

    # ── WELCOME ──────────────────────────────────────────────────────────────
    if phase == "welcome":
        text_lower = user_text.lower()
        complaint_intent = any(w in text_lower for w in COMPLAINT_INTENT_KEYWORDS)

        if complaint_intent:
            state["phase"] = "collecting"
            state["waiting_for"] = "name"
            reply = (
                "Mi dispiace per l'inconveniente. Per gestire correttamente la tua segnalazione "
                "ho bisogno di alcune informazioni:\n\n"
                "- Nome e cognome\n"
                "- Email di contatto\n"
                "- Prodotto acquistato\n"
                "- Codice lotto *(formato LT seguito da 5 cifre, es. LT12345)*\n"
                "- Data di scadenza *(se disponibile)*\n"
                "- Luogo di acquisto *(se disponibile)*\n"
                "- Descrizione del problema\n\n"
                "Puoi fornirmi tutte le informazioni insieme oppure una alla volta. "
                "Iniziamo: puoi dirmi il tuo **nome e cognome**?"
            )
            return reply, state, []

        if llm.is_configured(config):
            hist = conversation_history or []
            reply, suggestions = llm.generate_chat_reply(user_text, hist, state, config)
        else:
            reply, suggestions = _deterministic_reply(user_text, state)

        return reply, state, suggestions

    # ── COLLECTING ───────────────────────────────────────────────────────────
    if phase == "collecting":
        collected_before = dict(collected)

        wf = state.get("waiting_for")

        if llm.is_configured(config):
            collected = llm.extract_complaint_fields(user_text, collected, config, waiting_for=wf)
        else:
            collected = _extract_fields_regex(user_text, collected)
        if wf and not collected.get(wf):
            raw = user_text.strip()[:MAX_FIELD_LENGTH]
            if wf == "lot_code":
                # Search for a valid lot code anywhere in the message
                match = LOT_CODE_RE.search(raw)
                if match:
                    collected["lot_code"] = match.group(0).upper()
                else:
                    # User typed something but it doesn't contain a valid LT+5digit code
                    state["collected"] = collected
                    state["waiting_for"] = "lot_code"
                    return LOT_CODE_HINT, state, []
            else:
                collected[wf] = raw

        # Validate lot_code (must be exactly LT+5digits)
        if collected.get("lot_code") and not LOT_CODE_RE.fullmatch(collected["lot_code"].upper()):
            collected.pop("lot_code")
            state["collected"] = collected
            state["waiting_for"] = "lot_code"
            return LOT_CODE_HINT, state, []

        # Validate product against the known product list
        if collected.get("product") and collected["product"] not in PRODUCTS:
            # Try case-insensitive match first
            match = next((p for p in PRODUCTS if p.lower() == collected["product"].lower()), None)
            if match:
                collected["product"] = match
            else:
                collected.pop("product")
                # If we were specifically waiting for product, show the available list.
                # Also clear description if the LLM incorrectly stored the user's product
                # answer as a description (description was newly set this turn to the raw input).
                if wf == "product":
                    if (not collected_before.get("description")
                            and collected.get("description") == user_text.strip()):
                        collected.pop("description", None)
                    product_list = "\n".join(f"- {p}" for p in PRODUCTS)
                    state["collected"] = collected
                    state["waiting_for"] = "product"
                    return (
                        f"Non ho trovato quel prodotto tra quelli disponibili. "
                        f"Ecco i prodotti San Carlo:\n\n{product_list}\n\n"
                        "Puoi indicarmi quale hai acquistato?",
                        state, []
                    )

        state["collected"] = collected
        missing = get_missing_fields(collected)

        if not missing:
            # Deduce problem_category from description if not already extracted
            if not collected.get("problem_category"):
                collected["problem_category"] = _infer_category(
                    collected.get("description", "")
                )

            from modules.classifier import classify_complaint, assign_clusters
            result = classify_complaint(collected, config)
            cluster_result = assign_clusters(collected, config)
            complaint_data = {**collected, **result, **cluster_result, "channel": "chatbot"}
            complaint_id = save_complaint(complaint_data)
            state["complaint_id"] = complaint_id
            state["phase"] = "done"

            summary = build_summary(collected)
            ai_resp = result.get("ai_response", "")
            is_simple = result["classification"] == "semplice"

            base = f"✅ **Segnalazione #{complaint_id} registrata.**\n\n"
            base += f"Riepilogo informazioni ricevute:\n{summary}\n\n---\n"

            if ai_resp:
                reply = base + ai_resp
            elif is_simple:
                reply = (
                    base
                    + "La tua segnalazione è stata registrata e sarà utilizzata "
                    "per monitorare la qualità dei nostri prodotti.\n\n"
                    "Riceverai una email di conferma all'indirizzo indicato."
                )
            else:
                reply = (
                    base
                    + "Il reclamo sarà preso in carico dal nostro team qualità. "
                    "Riceverai un aggiornamento via email entro 2-3 giorni lavorativi."
                )
            suggestions = ["Grazie!", "Aprire un altro reclamo"]

        else:
            next_field = missing[0]
            state["waiting_for"] = next_field
            already = [f for f in REQUIRED_COMPLAINT_FIELDS if collected.get(f)]
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
