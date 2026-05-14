"""
Complaint classification.
classify_complaint() delegates to LLM when configured; falls back to _classify_mock().
"""
import logging

from modules.constants import COMPLEX_CATEGORIES, PRIORITY_MAP

logger = logging.getLogger(__name__)

SIMPLE_KEYWORDS = [
    "bruciata", "bruciate", "scura", "scure", "verde", "verdi",
    "sbriciolata", "sbriciolate", "rotta", "rotte", "salata",
    "leggera", "colore", "forma", "croccante",
]

COMPLEX_KEYWORDS = [
    "corpo estraneo", "estraneo", "capello", "insetto", "mosca",
    "vuota", "vuoto", "muffa", "ammuffita",
    "odore", "puzza", "contaminazione", "compromessa",
    "alterato", "alterata", "sicurezza", "metallo", "plastica", "vetro",
]


def classify_complaint(collected_data: dict | str, config: dict | str = None) -> dict:
    """
    Classify a complaint using LLM when configured, mock otherwise.

    Accepts two calling conventions:
    - classify_complaint(collected_dict, config_dict)  — standard path from chatbot
    - classify_complaint(category_str, description_str) — legacy path from init_data.py
    """
    from modules import llm as llm_module

    # Legacy call: classify_complaint("Categoria", "descrizione")
    if isinstance(collected_data, str):
        category = collected_data
        description = config if isinstance(config, str) else ""
        return _classify_mock(category, description)

    cfg = config or {}
    if llm_module.is_configured(cfg):
        return llm_module.classify_and_respond(collected_data, cfg)

    return _classify_mock(
        collected_data.get("problem_category", ""),
        collected_data.get("description", ""),
    )


def _classify_mock(problem_category: str, description: str) -> dict:
    """Keyword-based fallback classifier — no API needed."""
    text = (problem_category + " " + description).lower()

    is_complex = (
        any(kw in text for kw in COMPLEX_KEYWORDS)
        or problem_category in COMPLEX_CATEGORIES
    )

    classification = "complesso" if is_complex else "semplice"
    priority = PRIORITY_MAP.get(problem_category, "Bassa")

    if classification == "semplice":
        return {
            "classification": "semplice",
            "status": "Chiuso automaticamente",
            "priority": priority,
            "auto_response": True,
            "ai_response": _generate_auto_response(problem_category),
        }
    return {
        "classification": "complesso",
        "status": "Aperto",
        "priority": priority,
        "auto_response": False,
        "ai_response": _generate_complex_response(problem_category),
    }


def _generate_auto_response(category: str) -> str:
    responses = {
        "Patatina bruciata": (
            "Gentile Cliente,\n\n"
            "la ringraziamo per la sua segnalazione. In alcuni casi possono verificarsi "
            "leggere variazioni di colore nelle nostre patatine, dovute alle caratteristiche "
            "naturali delle patate e al processo di cottura ad alta temperatura. "
            "Si tratta di un fenomeno fisiologico che non compromette la sicurezza del prodotto.\n\n"
            "La sua segnalazione è stata registrata e sarà utilizzata dal nostro team qualità "
            "per monitorare i processi produttivi.\n\n"
            "Cordiali saluti,\nTeam Qualità San Carlo"
        ),
        "Patatina verde": (
            "Gentile Cliente,\n\n"
            "la ringraziamo per la sua segnalazione. Le patatine di colore verde derivano da "
            "patate che hanno subito un leggero processo di inverdimento per esposizione alla luce. "
            "I nostri controlli qualità prevedono la selezione di queste patate, ma in rari casi "
            "qualcuna può passare inosservata.\n\n"
            "La sua segnalazione è stata registrata e contribuirà a migliorare i nostri standard.\n\n"
            "Cordiali saluti,\nTeam Qualità San Carlo"
        ),
        "Prodotto sbriciolato": (
            "Gentile Cliente,\n\n"
            "la ringraziamo per la sua segnalazione. Durante il trasporto e la distribuzione "
            "possono verificarsi urti che causano la sbriciolatura di parte del contenuto. "
            "Stiamo lavorando per migliorare il packaging e ridurre al minimo questi inconvenienti.\n\n"
            "La sua segnalazione è stata registrata.\n\n"
            "Cordiali saluti,\nTeam Qualità San Carlo"
        ),
        "Gusto anomalo": (
            "Gentile Cliente,\n\n"
            "la ringraziamo per la sua segnalazione relativa a un gusto anomalo. "
            "Lievi variazioni organolettiche possono occasionalmente verificarsi per via "
            "delle caratteristiche naturali delle materie prime. "
            "La sua segnalazione è stata registrata e sarà analizzata dal nostro team.\n\n"
            "Cordiali saluti,\nTeam Qualità San Carlo"
        ),
        "Confezione danneggiata": (
            "Gentile Cliente,\n\n"
            "la ringraziamo per la sua segnalazione. La confezione potrebbe essere stata "
            "danneggiata durante il trasporto o la distribuzione. "
            "La sua segnalazione è stata registrata.\n\n"
            "Cordiali saluti,\nTeam Qualità San Carlo"
        ),
    }
    return responses.get(category, (
        "Gentile Cliente,\n\n"
        "la ringraziamo per la sua segnalazione. La sua segnalazione è stata registrata "
        "e sarà utilizzata per monitorare la qualità dei nostri prodotti.\n\n"
        "Cordiali saluti,\nTeam Qualità San Carlo"
    ))


def _generate_complex_response(category: str) -> str:
    return (
        "Gentile Cliente,\n\n"
        f"la ringraziamo per la sua segnalazione relativa a: **{category}**.\n\n"
        "Poiché il caso richiede una verifica più approfondita, il reclamo sarà preso in carico "
        "dal nostro team qualità che effettuerà le opportune verifiche.\n\n"
        "Riceverà un aggiornamento all'indirizzo email fornito entro 2-3 giorni lavorativi. "
        "La invitiamo a conservare la confezione.\n\n"
        "Cordiali saluti,\nTeam Qualità San Carlo"
    )
