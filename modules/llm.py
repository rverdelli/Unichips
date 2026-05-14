"""
Anthropic API layer for CarloBot.
All three public functions fall back gracefully to mock logic if the API is unavailable.
Swap the model string in get_client() or chatbot_config.json to upgrade.
"""
import json
import os
import re

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_api_key(config: dict) -> str | None:
    return (
        os.environ.get("ANTHROPIC_API_KEY")
        or config.get("anthropic_api_key")
        or None
    )


def _get_client(config: dict):
    if not _ANTHROPIC_AVAILABLE:
        return None
    key = _get_api_key(config)
    if not key:
        return None
    return anthropic.Anthropic(api_key=key)


def _model(config: dict) -> str:
    return config.get("model", DEFAULT_MODEL)


def _parse_json_block(text: str) -> dict:
    """Extract first JSON object from a string (handles markdown code fences)."""
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


# ── Public functions ─────────────────────────────────────────────────────────

def extract_complaint_fields(user_text: str, already_collected: dict, config: dict) -> dict:
    """
    Use Claude to extract structured complaint fields from free-form Italian text.
    Returns only the fields actually found in the message (no inference).
    Falls back to regex-based extraction on failure.
    """
    client = _get_client(config)
    if not client:
        from modules.chatbot import _extract_fields_regex
        return _extract_fields_regex(user_text, already_collected)

    common_knowledge = config.get("common_knowledge", "")
    already_str = json.dumps(already_collected, ensure_ascii=False)

    system = (
        "Sei un assistente per l'estrazione di informazioni da messaggi di clienti italiani "
        "che segnalano problemi con prodotti snack (patatine San Carlo).\n\n"
        f"Conoscenze di dominio:\n{common_knowledge}\n\n"
        "Prodotti possibili: Più Gusto Vivace, Più Gusto Lime e Pepe Rosa, Più Gusto Porchetta, "
        "Più Gusto Tartufo, Classica, Rustica, Veggy Good, Pop Corn San Carlo, Wacko's, Highlander.\n\n"
        "Categorie problema possibili: Patatina bruciata, Patatina verde, Prodotto sbriciolato, "
        "Gusto anomalo, Corpo estraneo, Confezione vuota, Confezione danneggiata, Odore anomalo, "
        "Muffa / alterazione, Altro.\n\n"
        "Estrai DAL MESSAGGIO DELL'UTENTE solo le informazioni esplicitamente presenti. "
        "NON inventare o inferire informazioni non menzionate. "
        "Rispondi SOLO con un oggetto JSON valido, senza testo aggiuntivo."
    )

    user_prompt = (
        f"Informazioni già raccolte (non ripetere): {already_str}\n\n"
        f"Messaggio del cliente: {user_text}\n\n"
        "Estrai le informazioni presenti nel messaggio. "
        "Campi possibili: name (nome e cognome), email, product (nome prodotto), "
        "problem_category (categoria problema), lot_code (codice lotto), "
        "description (descrizione problema), expiry_date (data scadenza), "
        "purchase_location (punto vendita).\n"
        "Includi SOLO i campi trovati nel messaggio. Rispondi con JSON."
    )

    try:
        response = client.messages.create(
            model=_model(config),
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        )
        result = _parse_json_block(response.content[0].text)
        # Merge with already collected, new fields take priority
        return {**already_collected, **{k: v for k, v in result.items() if v}}
    except Exception:
        from modules.chatbot import _extract_fields_regex
        return _extract_fields_regex(user_text, already_collected)


def generate_chat_reply(
    user_text: str,
    conversation_history: list,
    state: dict,
    config: dict,
) -> tuple[str, list]:
    """
    Use Claude to generate a natural conversational reply.
    Returns (reply_text, suggestions_list).
    Falls back to deterministic logic on failure.
    """
    client = _get_client(config)
    if not client:
        from modules.chatbot import _deterministic_reply
        return _deterministic_reply(user_text, state)

    common_knowledge = config.get("common_knowledge", "")
    classification_rules = config.get("classification_rules", "")
    phase = state.get("phase", "welcome")
    collected = state.get("collected", {})

    system = (
        "Sei CarloBot, l'assistente virtuale di San Carlo / Unichips. "
        "Parli sempre in italiano, con tono cordiale e professionale. "
        "Il tuo scopo è aiutare i consumatori con informazioni sui prodotti "
        "e guidarli nell'apertura di segnalazioni di qualità.\n\n"
        f"Conoscenze di dominio:\n{common_knowledge}\n\n"
        f"Regole di classificazione reclami:\n{classification_rules}\n\n"
        "Rispondi in modo conciso e utile. "
        "Se l'utente vuole aprire un reclamo, incoraggialo e guida la raccolta dati. "
        "Per domande generiche rispondi con le informazioni disponibili e offri suggerimenti.\n\n"
        "Alla fine della tua risposta, su una riga separata, scrivi SUGGESTIONS: seguito da "
        "una lista JSON di 0-3 suggerimenti brevi per l'utente (stringhe). "
        "Esempio: SUGGESTIONS: [\"Voglio aprire un reclamo\", \"Dove trovo il lotto?\"]"
    )

    messages = []
    for msg in conversation_history[-10:]:  # last 10 messages for context
        role = "assistant" if msg["role"] == "bot" else "user"
        messages.append({"role": role, "content": msg["text"]})
    messages.append({"role": "user", "content": user_text})

    try:
        response = client.messages.create(
            model=_model(config),
            max_tokens=600,
            system=system,
            messages=messages,
        )
        full_text = response.content[0].text

        # Parse suggestions from the special marker
        suggestions = []
        if "SUGGESTIONS:" in full_text:
            parts = full_text.split("SUGGESTIONS:", 1)
            reply_text = parts[0].strip()
            sug_raw = parts[1].strip()
            try:
                suggestions = json.loads(sug_raw)
                if not isinstance(suggestions, list):
                    suggestions = []
            except json.JSONDecodeError:
                suggestions = []
        else:
            reply_text = full_text.strip()

        return reply_text, suggestions

    except Exception:
        from modules.chatbot import _deterministic_reply
        return _deterministic_reply(user_text, state)


def classify_and_respond(collected_data: dict, config: dict) -> dict:
    """
    Use Claude to classify the complaint and generate a personalized customer response.
    Returns dict with: classification, status, priority, auto_response, ai_response.
    Falls back to keyword-based classifier on failure.
    """
    client = _get_client(config)
    if not client:
        from modules.classifier import _classify_mock
        return _classify_mock(
            collected_data.get("problem_category", ""),
            collected_data.get("description", ""),
        )

    classification_rules = config.get("classification_rules", "")

    system = (
        "Sei un esperto di qualità alimentare per San Carlo / Unichips. "
        "Ricevi i dati di un reclamo cliente e devi:\n"
        "1. Classificare il reclamo come 'semplice' (risposta automatica possibile) "
        "o 'complesso' (richiede verifica del team qualità)\n"
        "2. Determinare la priorità: 'Alta', 'Media', 'Bassa'\n"
        "3. Generare una risposta professionale in italiano da inviare al cliente\n\n"
        f"Regole di classificazione:\n{classification_rules}\n\n"
        "Rispondi SOLO con un oggetto JSON valido con questi campi:\n"
        "- classification: 'semplice' o 'complesso'\n"
        "- status: 'Chiuso automaticamente' (se semplice) o 'Aperto' (se complesso)\n"
        "- priority: 'Alta', 'Media' o 'Bassa'\n"
        "- auto_response: true (se semplice) o false (se complesso)\n"
        "- ai_response: risposta professionale completa in italiano da inviare al cliente "
        "(con intestazione 'Gentile Cliente,' e firma 'Team Qualità San Carlo')"
    )

    complaint_str = "\n".join(
        f"- {k}: {v}" for k, v in collected_data.items() if v and k != "channel"
    )

    user_prompt = f"Dati del reclamo:\n{complaint_str}\n\nClassifica e genera la risposta."

    try:
        response = client.messages.create(
            model=_model(config),
            max_tokens=800,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        )
        result = _parse_json_block(response.content[0].text)

        # Validate and normalise
        classification = result.get("classification", "semplice")
        if classification not in ("semplice", "complesso"):
            classification = "semplice"

        status_map = {"semplice": "Chiuso automaticamente", "complesso": "Aperto"}
        priority = result.get("priority", "Bassa")
        if priority not in ("Alta", "Media", "Bassa"):
            priority = "Bassa"

        return {
            "classification": classification,
            "status": result.get("status", status_map[classification]),
            "priority": priority,
            "auto_response": result.get("auto_response", classification == "semplice"),
            "ai_response": result.get("ai_response", ""),
        }

    except Exception:
        from modules.classifier import _classify_mock
        return _classify_mock(
            collected_data.get("problem_category", ""),
            collected_data.get("description", ""),
        )


def is_configured(config: dict) -> bool:
    """Returns True if a valid API key is available."""
    return bool(_get_api_key(config))
