"""
Chatbot conversation logic (state machine).
LLM calls are delegated to modules/llm.py — swap API key to go live.
"""
import logging
import html
import json
import re
import unicodedata

from modules.database import save_complaint, get_chatbot_config
from modules.constants import (
    REQUIRED_COMPLAINT_FIELDS, FIELD_LABELS, FIELD_PROMPTS,
    PRODUCTS as DEFAULT_PRODUCTS, CATEGORIES, COMPLAINT_INTENT_KEYWORDS,
)

logger = logging.getLogger(__name__)

MAX_FIELD_LENGTH = 1000  # Guard against absurdly long inputs
BULK_MESSAGE_MIN_LENGTH = 180
MAX_CONVERSATION_MESSAGES = 200
MAX_CONVERSATION_TEXT_LENGTH = 5000


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


def _plain_message_text(value) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False)
        except TypeError:
            value = str(value)

    text = re.sub(r"(?i)<br\s*/?>", "\n", value)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"</?[a-z][a-z0-9-]*(?:\s+[^>]*)?>", "", text)
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:MAX_CONVERSATION_TEXT_LENGTH]


def _normalise_history_role(role) -> str:
    value = str(role or "").strip().lower()
    if value in ("user", "cliente", "customer"):
        return "user"
    return "bot"


def _append_conversation_turn(items: list[dict], role: str, text: str | None):
    clean_text = _plain_message_text(text)
    if not clean_text:
        return
    clean_role = _normalise_history_role(role)
    if items and items[-1].get("role") == clean_role and items[-1].get("text") == clean_text:
        return
    items.append({"role": clean_role, "text": clean_text})


def build_conversation_history(
    conversation_history: list | None,
    user_text: str | None = None,
    bot_reply: str | None = None,
) -> list[dict]:
    items: list[dict] = []
    for msg in conversation_history or []:
        if not isinstance(msg, dict):
            continue
        _append_conversation_turn(
            items,
            msg.get("role"),
            msg.get("raw_text") or msg.get("text") or msg.get("content") or msg.get("message"),
        )
    _append_conversation_turn(items, "user", user_text)
    _append_conversation_turn(items, "bot", bot_reply)
    return items[-MAX_CONVERSATION_MESSAGES:]


LOT_CODE_RE = re.compile(r'\bLT\d{5}\b', re.IGNORECASE)
LOT_CODE_HINT = (
    "Il codice lotto deve essere nel formato **LT seguito da 5 cifre** "
    "(es. `LT12345`). Lo trovi sul retro o sul bordo della confezione, "
    "vicino alla data di scadenza. Puoi riprovare?"
)
PHOTO_REQUIRED_HINT = (
    "Ho raccolto tutte le informazioni testuali, ma per registrare il reclamo "
    "mi serve almeno una foto del prodotto/confezione. Carica una o piu' immagini "
    "con il pulsante qui sopra, poi scrivimi pure **foto caricate**."
)

EMAIL_RE = re.compile(r"[\w.\-+]+@[\w.\-]+\.[a-zA-Z]{2,}")

_KNOWN_INPUT_LABEL_RE = re.compile(
    r"^\s*(?:nome(?:\s+e\s+cognome)?|cliente|nominativo|email|e-mail|mail|"
    r"prodotto|codice\s+lotto|lotto|scadenza|tmc|punto\s+vendita|"
    r"luogo\s+di\s+acquisto|negozio|supermercato|descrizione|problema|"
    r"messaggio|testo|segnalazione|da|from|a|to|cc|oggetto|subject|data|date)"
    r"\s*[:=\-]",
    re.IGNORECASE | re.MULTILINE,
)

_EMAIL_HEADER_RE = re.compile(r"^\s*(?:da|from)\s*[:=\-]\s*(.+)$", re.IGNORECASE | re.MULTILINE)

_ISSUE_KEYWORDS = (
    "bruciata", "bruciate", "bruciato", "scura", "nera", "carbonizzata",
    "verde", "verdi", "sbriciolata", "sbriciolato", "rotte", "rotto",
    "frantumata", "polvere", "gusto strano", "sapore strano", "retrogusto",
    "amaro", "metallico", "corpo estraneo", "capello", "insetto", "plastica",
    "metallo", "vetro", "frammento", "vuota", "vuoto", "danneggiata",
    "aperta", "strappata", "busta rotta", "odore", "puzza", "rancido",
    "sgradevole", "muffa", "ammuffita", "alterazione", "difetto",
)


def _normalise_for_matching(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _truncate(value: str) -> str:
    return (value or "").strip()[:MAX_FIELD_LENGTH]


def _products_from_config(config: dict | None) -> list[str]:
    products = (config or {}).get("products") or DEFAULT_PRODUCTS
    clean = []
    seen = set()
    for product in products:
        value = str(product).strip()
        key = value.lower()
        if value and key not in seen:
            clean.append(value)
            seen.add(key)
    return clean or list(DEFAULT_PRODUCTS)


def _has_problem_detail(text: str) -> bool:
    norm = _normalise_for_matching(text)
    return any(kw in norm for kw in _ISSUE_KEYWORDS)


def _first_labeled_value(text: str, labels: list[str]) -> str | None:
    label_alt = "|".join(re.escape(label) for label in labels)
    pattern = re.compile(rf"(?im)^\s*(?:{label_alt})\s*[:=\-]\s*(.+?)\s*$")
    match = pattern.search(text or "")
    if not match:
        return None
    value = match.group(1).strip()
    return _truncate(value) if value else None


def _labeled_multiline_value(text: str, labels: list[str]) -> str | None:
    label_alt = "|".join(re.escape(label) for label in labels)
    start_re = re.compile(rf"^\s*(?:{label_alt})\s*[:=\-]\s*(.*)$", re.IGNORECASE)
    lines = (text or "").splitlines()

    for i, line in enumerate(lines):
        match = start_re.match(line)
        if not match:
            continue

        parts = []
        first = match.group(1).strip()
        if first:
            parts.append(first)

        for next_line in lines[i + 1:]:
            stripped = next_line.strip()
            if not stripped:
                if parts:
                    break
                continue
            if stripped.startswith(">") or _KNOWN_INPUT_LABEL_RE.match(stripped):
                break
            if re.match(r"(?i)^(cordiali saluti|saluti|grazie|inviato da)\b", stripped):
                break
            parts.append(stripped)

        value = " ".join(parts).strip()
        if value:
            return _truncate(value)

    return None


def _clean_name_candidate(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"<[^>]+>", " ", value)
    value = EMAIL_RE.sub(" ", value)
    value = re.sub(r"\b(?:mailto|tel)\s*:\s*\S+", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"[\"'<>|]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" ,;-")
    norm = _normalise_for_matching(value)

    bad_fragments = (
        "san carlo", "servizio clienti", "assistenza", "noreply", "no reply",
        "rimasta", "rimasto", "delusa", "deluso", "arrabbiata", "arrabbiato",
        "insoddisfatta", "insoddisfatto", "scrivo", "contatto",
    )
    if not value or any(bad in norm for bad in bad_fragments) or _has_problem_detail(value):
        return None
    if any(token in norm for token in ("http", "www", "oggetto", "subject", "reclamo")):
        return None

    words = [w for w in value.split() if re.search(r"[A-Za-z]", w)]
    if len(words) < 2 or len(words) > 6:
        return None
    return _truncate(" ".join(words))


def _extract_name(text: str) -> str | None:
    labeled = _first_labeled_value(text, ["nome", "nome e cognome", "cliente", "nominativo"])
    name = _clean_name_candidate(labeled)
    if name:
        return name

    header = _EMAIL_HEADER_RE.search(text or "")
    if header:
        name = _clean_name_candidate(header.group(1))
        if name:
            return name

    match = re.search(r"(?i)\b(?:mi chiamo|sono)\s+([^,\n\r.;]+)", text or "")
    if match:
        candidate = re.split(r"(?i)\s+(?:e|vi|le)\s+", match.group(1), maxsplit=1)[0]
        return _clean_name_candidate(candidate)

    return None


def _product_with_fragment(fragment: str, products: list[str] | None = None) -> str | None:
    for product in products or DEFAULT_PRODUCTS:
        if fragment in _normalise_for_matching(product):
            return product
    return None


def _match_known_product(text: str, products: list[str] | None = None) -> str | None:
    products = products or DEFAULT_PRODUCTS
    norm = _normalise_for_matching(text)
    if not norm:
        return None

    for product in products:
        product_norm = _normalise_for_matching(product)
        if product_norm and product_norm in norm:
            return product

    aliases = [
        ("piu gusto lime pepe rosa", "lime"),
        ("lime pepe rosa", "lime"),
        ("piu gusto porchetta", "porchetta"),
        ("porchetta", "porchetta"),
        ("piu gusto tartufo", "tartufo"),
        ("tartufo", "tartufo"),
        ("piu gusto vivace", "vivace"),
        ("vivace", "vivace"),
        ("patatine classiche", "classica"),
        ("patatina classica", "classica"),
        ("classiche", "classica"),
        ("classica", "classica"),
        ("rustiche", "rustica"),
        ("rustica", "rustica"),
        ("veggy good", "veggy"),
        ("veggy", "veggy"),
        ("pop corn", "pop corn"),
        ("popcorn", "pop corn"),
        ("wacko", "wacko"),
        ("highlander", "highlander"),
    ]
    for alias, product_fragment in aliases:
        if alias in norm:
            product = _product_with_fragment(product_fragment, products)
            if product:
                return product

    return None


def _extract_expiry_date(text: str) -> str | None:
    labeled = _first_labeled_value(text, ["scadenza", "data scadenza", "data di scadenza", "tmc"])
    if labeled:
        return labeled

    match = re.search(
        r"(?i)\b(?:scadenza|tmc|da consumarsi preferibilmente entro)\b\s*[:=\-]?\s*"
        r"(\d{1,2}[\/.\-]\d{1,2}[\/.\-]\d{2,4}|\d{1,2}[\/.\-]\d{2,4})",
        text or "",
    )
    return _truncate(match.group(1)) if match else None


def _extract_purchase_location(text: str) -> str | None:
    labeled = _first_labeled_value(
        text,
        ["punto vendita", "luogo di acquisto", "negozio", "supermercato", "acquistato presso"],
    )
    if labeled:
        return labeled

    match = re.search(
        r"(?i)\b(?:acquistat[oa]|comprat[oa])\s+(?:presso|da|al|alla)\s+([^,\n\r.;]+)",
        text or "",
    )
    return _truncate(match.group(1)) if match else None


def _strip_email_boilerplate(text: str) -> str:
    cleaned = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(">"):
            continue
        if re.match(r"(?i)^(buongiorno|buonasera|salve|ciao)[,!. ]*$", stripped):
            continue
        if re.match(r"(?i)^(da|from|a|to|cc|oggetto|subject|data|date|inviato|sent)\s*[:=\-]", stripped):
            continue
        if re.match(r"(?i)^(nome|nome e cognome|cliente|nominativo|email|e-mail|mail|prodotto|codice lotto|lotto|scadenza|tmc|punto vendita|luogo di acquisto|negozio|supermercato)\s*[:=\-]", stripped):
            continue
        if re.match(r"(?i)^(cordiali saluti|saluti|grazie|inviato da)\b", stripped):
            break
        cleaned.append(stripped)
    return _truncate(" ".join(cleaned))


def _extract_description(text: str) -> str | None:
    labeled = _labeled_multiline_value(text, ["descrizione", "problema", "messaggio", "testo", "segnalazione"])
    if labeled and (_has_problem_detail(labeled) or len(labeled) >= 30):
        return labeled

    body = _strip_email_boilerplate(text)
    if not body:
        return None
    norm = _normalise_for_matching(body)
    generic_only = norm in {
        "voglio aprire un reclamo",
        "voglio sottoporre un reclamo",
        "aprire un reclamo",
        "reclamo",
        "segnalazione",
    }
    if generic_only:
        return None
    if len(body) < 35 and not _has_problem_detail(body):
        return None
    return body


def _looks_like_bulk_message(text: str, products: list[str] | None = None) -> bool:
    if not text:
        return False
    non_empty_lines = [line for line in text.splitlines() if line.strip()]
    if len(non_empty_lines) >= 3 or len(text) >= BULK_MESSAGE_MIN_LENGTH:
        return True

    signals = 0
    signals += 1 if EMAIL_RE.search(text) else 0
    signals += 1 if LOT_CODE_RE.search(text) else 0
    signals += 1 if _match_known_product(text, products) else 0
    signals += 1 if _KNOWN_INPUT_LABEL_RE.search(text) else 0
    signals += 1 if _has_problem_detail(text) else 0
    return signals >= 3


def _looks_like_complaint_payload(text: str, products: list[str] | None = None) -> bool:
    text_lower = (text or "").lower()
    complaint_intent = any(w in text_lower for w in COMPLAINT_INTENT_KEYWORDS)
    if complaint_intent:
        return True

    core_signals = 0
    core_signals += 1 if EMAIL_RE.search(text or "") else 0
    core_signals += 1 if LOT_CODE_RE.search(text or "") else 0
    core_signals += 1 if _match_known_product(text or "", products) else 0
    core_signals += 1 if _has_problem_detail(text or "") else 0
    return _looks_like_bulk_message(text or "", products) and core_signals >= 2


def _coerce_waiting_field_answer(field: str, text: str, products: list[str] | None = None) -> str | None:
    raw = _truncate(text)
    if not raw or _looks_like_bulk_message(raw, products):
        return None
    if field == "name":
        return _clean_name_candidate(raw)
    if field == "email":
        match = EMAIL_RE.search(raw)
        return match.group(0) if match else None
    if field == "product":
        return _match_known_product(raw, products)
    if field == "lot_code":
        match = LOT_CODE_RE.search(raw)
        return match.group(0).upper() if match else None
    if field == "description":
        return raw if len(raw) >= 10 else None
    return raw


def _collection_intro() -> str:
    return (
        "Mi dispiace per l'inconveniente. Per gestire correttamente la tua segnalazione "
        "ho bisogno di alcune informazioni:\n\n"
        "- Nome e cognome\n"
        "- Email di contatto\n"
        "- Prodotto acquistato\n"
        "- Codice lotto *(formato LT seguito da 5 cifre, es. LT12345)*\n"
        "- Data di scadenza *(se disponibile)*\n"
        "- Luogo di acquisto *(se disponibile)*\n"
        "- Descrizione del problema\n\n"
        "Puoi incollare anche una mail intera: leggero' tutti i dati disponibili in un blocco solo.\n\n"
        "Iniziamo: puoi dirmi il tuo **nome e cognome**?"
    )


# ── Fallback: regex-based extraction (used when API unavailable) ─────────────

def _extract_fields_regex(text: str, collected: dict, products: list[str] | None = None) -> dict:
    updated = dict(collected)
    products = products or DEFAULT_PRODUCTS

    if not updated.get("name"):
        name = _extract_name(text)
        if name:
            updated["name"] = name

    email_match = EMAIL_RE.search(text)
    if email_match and not updated.get("email"):
        updated["email"] = email_match.group(0)

    lot_match = LOT_CODE_RE.search(text)
    if lot_match and not updated.get("lot_code"):
        updated["lot_code"] = lot_match.group(0).upper()

    if not updated.get("product"):
        labeled_product = _first_labeled_value(text, ["prodotto", "prodotto acquistato"])
        product = _match_known_product(labeled_product or text, products)
        if product:
            updated["product"] = product

    if not updated.get("expiry_date"):
        expiry_date = _extract_expiry_date(text)
        if expiry_date:
            updated["expiry_date"] = expiry_date

    if not updated.get("purchase_location"):
        purchase_location = _extract_purchase_location(text)
        if purchase_location:
            updated["purchase_location"] = purchase_location

    if not updated.get("description"):
        description = _extract_description(text)
        if description:
            updated["description"] = description

    if not updated.get("problem_category"):
        text_lower = (updated.get("description") or text).lower()
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
    products = _products_from_config(config)
    phase = state.get("phase", "welcome")
    collected = state.get("collected", {})
    suggestions: list[str] = []
    started_from_welcome = False

    # ── WELCOME ──────────────────────────────────────────────────────────────
    if phase == "welcome":
        if _looks_like_complaint_payload(user_text, products):
            state["phase"] = "collecting"
            state["waiting_for"] = None
            phase = "collecting"
            started_from_welcome = True
            collected = state.get("collected", {})
        else:
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

        deterministic_collected = _extract_fields_regex(user_text, collected, products)
        if llm.is_configured(config):
            llm_collected = llm.extract_complaint_fields(user_text, collected, config, waiting_for=wf)
            collected = {
                **deterministic_collected,
                **{k: v for k, v in llm_collected.items() if v},
            }
        else:
            collected = deterministic_collected

        if wf and not collected.get(wf):
            coerced = _coerce_waiting_field_answer(wf, user_text, products)
            if coerced:
                collected[wf] = coerced
            elif wf == "lot_code" and not _looks_like_bulk_message(user_text, products):
                state["collected"] = collected
                state["waiting_for"] = "lot_code"
                return LOT_CODE_HINT, state, []

        for key, value in list(collected.items()):
            if isinstance(value, str):
                collected[key] = _truncate(value)

        # Validate lot_code (must be exactly LT+5digits)
        if collected.get("lot_code"):
            collected["lot_code"] = collected["lot_code"].upper()
            if not LOT_CODE_RE.fullmatch(collected["lot_code"]):
                collected.pop("lot_code")
                state["collected"] = collected
                state["waiting_for"] = "lot_code"
                return LOT_CODE_HINT, state, []

        # Validate product against the known product list
        if collected.get("product"):
            match = _match_known_product(collected["product"], products)
            if match:
                collected["product"] = match
            elif collected["product"] not in products:
                collected.pop("product")
                # If we were specifically waiting for product, show the available list.
                # Also clear description if the LLM incorrectly stored the user's product
                # answer as a description (description was newly set this turn to the raw input).
                if wf == "product":
                    if (not collected_before.get("description")
                            and collected.get("description") == user_text.strip()):
                        collected.pop("description", None)
                    product_list = "\n".join(f"- {p}" for p in products)
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
            if not collected.get("has_photo"):
                state["collected"] = collected
                state["waiting_for"] = "photo"
                return PHOTO_REQUIRED_HINT, state, []

            # Deduce problem_category from description if not already extracted
            if not collected.get("problem_category"):
                collected["problem_category"] = _infer_category(
                    collected.get("description", "")
                )

            from modules.classifier import process_complaint
            result = process_complaint(collected, config)
            complaint_data = {
                **collected,
                **result,
                "channel": "chatbot",
                "conversation_history": build_conversation_history(
                    conversation_history,
                    user_text,
                ),
            }
            complaint_id = save_complaint(complaint_data)
            state["complaint_id"] = complaint_id
            state["phase"] = "done"
            state["waiting_for"] = None

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
            elif started_from_welcome:
                reply = _collection_intro()
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
