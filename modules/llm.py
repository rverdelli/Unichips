"""
Anthropic API layer for CarloBot.
All three public functions fall back gracefully to mock logic if the API is unavailable.
Swap the model string in chatbot_config.json field "model" to upgrade.
"""
import json
import logging
import os
import re

logger = logging.getLogger(__name__)

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
    """
    Extract the first well-formed JSON object from a string.
    Uses a brace-counting scan rather than a greedy regex to handle
    nested objects correctly.
    """
    start = text.find("{")
    if start == -1:
        return {}
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start: i + 1])
                except json.JSONDecodeError as e:
                    logger.warning("JSON parse failed: %s", e)
                    return {}
    return {}


# ── Public functions ─────────────────────────────────────────────────────────

def extract_complaint_fields(user_text: str, already_collected: dict, config: dict, waiting_for: str | None = None) -> dict:
    """
    Use Claude to extract structured complaint fields from free-form Italian text.
    Returns only the fields actually found in the message (no inference).
    Falls back to regex-based extraction on API failure.
    """
    from modules.chatbot import _extract_fields_regex  # local import avoids circular at module level

    client = _get_client(config)
    if not client:
        return _extract_fields_regex(user_text, already_collected)

    from modules.constants import PRODUCTS, CATEGORIES

    already_str = json.dumps(already_collected, ensure_ascii=False)
    common_knowledge = config.get("common_knowledge", "")

    system = (
        "Sei un assistente per l'estrazione di informazioni da messaggi di clienti italiani "
        "che segnalano problemi con prodotti snack (patatine San Carlo).\n\n"
        f"Conoscenze di dominio:\n{common_knowledge}\n\n"
        f"Prodotti possibili: {', '.join(PRODUCTS)}.\n\n"
        f"Categorie problema possibili: {', '.join(CATEGORIES)}.\n\n"
        "Estrai DAL MESSAGGIO DELL'UTENTE solo le informazioni esplicitamente presenti. "
        "NON inventare o inferire informazioni non menzionate. "
        "Rispondi SOLO con un oggetto JSON valido, senza testo aggiuntivo."
    )

    waiting_hint = (
        f"\nATTENZIONE: il bot sta aspettando il campo '{waiting_for}'. "
        "Il messaggio del cliente è probabilmente una risposta a questa domanda specifica. "
        f"Prova ad estrarre prima di tutto il campo '{waiting_for}'. "
        "NON inserire il testo in un campo diverso (es. non mettere il nome di un prodotto in 'description').\n"
        if waiting_for else ""
    )

    user_prompt = (
        f"Informazioni già raccolte (non ripetere): {already_str}\n\n"
        f"Messaggio del cliente: {user_text}\n\n"
        "Estrai le informazioni presenti nel messaggio. "
        "Campi possibili: name (nome e cognome), email, product (nome prodotto), "
        "lot_code (codice lotto), description (descrizione problema), "
        "expiry_date (data scadenza), purchase_location (punto vendita).\n"
        "NON estrarre problem_category: verrà dedotta automaticamente dalla descrizione.\n"
        "IMPORTANTE: lot_code deve essere esattamente nel formato LT seguito da 5 cifre (es. LT12345). "
        "Se il testo contiene un codice lotto con formato diverso, NON includerlo nel JSON.\n"
        f"IMPORTANTE: il campo product deve essere ESATTAMENTE uno di questi valori: {', '.join(PRODUCTS)}. "
        "Se il cliente menziona un gusto o sapore (es. 'paprika', 'classica', 'tartufo') cerca di abbinarlo "
        "al nome prodotto corretto della lista. Se non riesci ad abbinarlo con certezza, NON includere il campo product.\n"
        + waiting_hint +
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
        return {**already_collected, **{k: v for k, v in result.items() if v}}
    except Exception as e:
        logger.error("extract_complaint_fields failed: %s", e)
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
    Falls back to deterministic logic on API failure.
    """
    from modules.chatbot import _deterministic_reply  # local import avoids circular at module level

    client = _get_client(config)
    if not client:
        return _deterministic_reply(user_text, state)

    common_knowledge = config.get("common_knowledge", "")

    system = (
        "Sei CarloBot, l'assistente virtuale di San Carlo / Unichips. "
        "Parli sempre in italiano, con tono cordiale e professionale. "
        "Il tuo scopo è aiutare i consumatori con informazioni sui prodotti "
        "e guidarli nell'apertura di segnalazioni di qualità.\n\n"
        f"Conoscenze di dominio:\n{common_knowledge}\n\n"
        "Rispondi in modo conciso e utile. "
        "Se l'utente vuole aprire un reclamo, incoraggialo e guida la raccolta dati. "
        "Per domande generiche rispondi con le informazioni disponibili e offri suggerimenti.\n\n"
        "Alla fine della tua risposta, su una riga separata, scrivi SUGGESTIONS: seguito da "
        "una lista JSON di 0-3 suggerimenti brevi per l'utente (stringhe). "
        'Esempio: SUGGESTIONS: ["Voglio aprire un reclamo", "Dove trovo il lotto?"]'
    )

    messages = []
    for msg in conversation_history[-10:]:
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

        suggestions: list[str] = []
        if "SUGGESTIONS:" in full_text:
            parts = full_text.split("SUGGESTIONS:", 1)
            reply_text = parts[0].strip()
            sug_raw = parts[1].strip()
            # Find JSON array
            arr_match = re.search(r"\[.*?\]", sug_raw, re.DOTALL)
            if arr_match:
                try:
                    suggestions = json.loads(arr_match.group(0))
                    if not isinstance(suggestions, list):
                        suggestions = []
                except json.JSONDecodeError as e:
                    logger.warning("Suggestions parse failed: %s", e)
                    suggestions = []
        else:
            reply_text = full_text.strip()

        return reply_text, suggestions

    except Exception as e:
        logger.error("generate_chat_reply failed: %s", e)
        return _deterministic_reply(user_text, state)


def process_complaint_with_clusters(collected: dict, clusters: list, config: dict) -> dict:
    """
    Single LLM call: assign cluster + derive classification from gravity + generate response.
    - Alta  → complesso → escalation, rimborso + buono €5
    - Media/Bassa → semplice → risposta informativa, nessun rimborso
    Falls back to empty dict on failure (caller handles fallback).
    """
    client = _get_client(config)
    if not client:
        return {}

    cluster_list = json.dumps(
        [{"cluster1": c["cluster1"], "cluster2": c["cluster2"],
          "gravity": c.get("gravity", ""), "example": c.get("example", "")}
         for c in clusters],
        ensure_ascii=False,
    )

    complaint_str = "\n".join(
        f"- {k}: {v}" for k, v in collected.items()
        if v and k not in ("channel", "has_photo", "problem_category")
    )
    customer_name = collected.get("name", "Cliente")

    system = (
        "Sei un esperto di qualità alimentare per San Carlo / Unichips. "
        "Ricevi i dati di un reclamo e devi:\n"
        "1. Assegnare il cluster di difetto più appropriato dalla lista fornita\n"
        "2. Generare una risposta professionale in italiano da inviare al cliente\n\n"
        "La classificazione è determinata dalla gravità del cluster assegnato:\n"
        "- Alta → complesso: scuse sincere, rimborso completo del prodotto + buono acquisto €5, "
        "  il team la contatterà entro 24h, conservare la confezione\n"
        "- Media/Bassa → semplice: spiegazione cordiale della causa naturale o tecnica, "
        "  nessun rimborso, segnalazione registrata per miglioramento qualità\n\n"
        "Rispondi SOLO con un oggetto JSON con i campi:\n"
        "- cluster1: esattamente dalla lista fornita\n"
        "- cluster2: esattamente dalla lista fornita\n"
        "- gravity: 'Alta', 'Media' o 'Bassa' (dal cluster scelto)\n"
        f"- ai_response: risposta completa in italiano (inizia con 'Gentile {customer_name},' "
        "  e termina con 'Team Qualità San Carlo')"
    )

    try:
        response = client.messages.create(
            model=_model(config),
            max_tokens=900,
            system=system,
            messages=[{"role": "user", "content":
                f"Dati del reclamo:\n{complaint_str}\n\n"
                f"Cluster disponibili:\n{cluster_list}\n\n"
                "Assegna il cluster e genera la risposta."}],
        )
        result = _parse_json_block(response.content[0].text)

        if not (result.get("cluster1") and result.get("cluster2")):
            return {}

        gravity = result.get("gravity", "Media")
        if gravity not in ("Alta", "Media", "Bassa"):
            gravity = "Media"

        is_complex = gravity == "Alta"
        return {
            "cluster1":       result["cluster1"],
            "cluster2":       result["cluster2"],
            "gravity":        gravity,
            "priority":       gravity,
            "classification": "complesso" if is_complex else "semplice",
            "status":         "Aperto" if is_complex else "Chiuso automaticamente",
            "auto_response":  not is_complex,
            "ai_response":    result.get("ai_response", ""),
        }

    except Exception as e:
        logger.error("process_complaint_with_clusters failed: %s", e)
        return {}


def is_configured(config: dict) -> bool:
    """Returns True if a valid API key is available."""
    return bool(_get_api_key(config))
