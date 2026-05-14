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
    priority = PRIORITY_MAP.get(problem_category, "Media")

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
            "la ringraziamo per averci contattato. Le patatine leggermente più scure del solito "
            "sono un fenomeno del tutto naturale: dipende dalla composizione in zuccheri delle patate, "
            "che possono dorarsi in modo più intenso durante la frittura. "
            "Non si tratta di un difetto di qualità né di un rischio per la salute.\n\n"
            "Abbiamo registrato la sua segnalazione e la utilizzeremo per monitorare i nostri processi produttivi.\n\n"
            "Cordiali saluti,\nTeam Qualità San Carlo"
        ),
        "Patatina verde": (
            "Gentile Cliente,\n\n"
            "la ringraziamo per la segnalazione. Le patatine verdi derivano da patate che hanno subito "
            "un leggero processo di inverdimento per esposizione alla luce prima della lavorazione. "
            "I nostri controlli di qualità prevedono la selezione ottica di queste patate, "
            "ma in rari casi qualcuna può sfuggire al processo.\n\n"
            "Abbiamo registrato la sua segnalazione e la utilizzeremo per migliorare i nostri standard.\n\n"
            "Cordiali saluti,\nTeam Qualità San Carlo"
        ),
        "Prodotto sbriciolato": (
            "Gentile Cliente,\n\n"
            "la ringraziamo per la segnalazione. La sbriciolatura del prodotto può avvenire durante "
            "il trasporto o la distribuzione a causa di urti o pressioni sulle confezioni. "
            "Il prodotto rimane comunque integro e sicuro dal punto di vista alimentare.\n\n"
            "Abbiamo preso nota della sua segnalazione e la trasmetteremo al team logistico "
            "per migliorare la gestione del packaging.\n\n"
            "Cordiali saluti,\nTeam Qualità San Carlo"
        ),
        "Gusto anomalo": (
            "Gentile Cliente,\n\n"
            "la ringraziamo per la segnalazione. Lievi variazioni di gusto possono occasionalmente "
            "verificarsi in base alle caratteristiche naturali delle materie prime "
            "o alle condizioni di conservazione del prodotto.\n\n"
            "Le chiediamo di conservare la confezione con il codice lotto visibile: "
            "il nostro team qualità verificherà il lotto di produzione indicato.\n\n"
            "Cordiali saluti,\nTeam Qualità San Carlo"
        ),
        "Confezione danneggiata": (
            "Gentile Cliente,\n\n"
            "la ringraziamo per la segnalazione. La confezione potrebbe essersi danneggiata "
            "durante il trasporto o la distribuzione.\n\n"
            "Abbiamo registrato la sua segnalazione e la trasmetteremo al team logistico "
            "per le opportune verifiche sulla catena di distribuzione.\n\n"
            "Cordiali saluti,\nTeam Qualità San Carlo"
        ),
    }
    return responses.get(category, (
        "Gentile Cliente,\n\n"
        "la ringraziamo per la sua segnalazione. Abbiamo registrato il suo feedback "
        "e lo utilizzeremo per migliorare la qualità dei nostri prodotti.\n\n"
        "Cordiali saluti,\nTeam Qualità San Carlo"
    ))


def _generate_complex_response(category: str) -> str:
    specific = {
        "Corpo estraneo": (
            "abbiamo ricevuto la sua segnalazione relativa al ritrovamento di un corpo estraneo "
            "nel prodotto. Si tratta di una segnalazione che prendiamo con la massima serietà."
        ),
        "Muffa / alterazione": (
            "abbiamo ricevuto la sua segnalazione relativa a un prodotto alterato o con presenza "
            "di muffa. È una situazione che non dovrebbe mai verificarsi e la prendiamo molto seriamente."
        ),
        "Odore anomalo": (
            "abbiamo ricevuto la sua segnalazione relativa a un odore anomalo nel prodotto. "
            "Questo tipo di segnalazione richiede una verifica approfondita da parte del nostro team."
        ),
        "Confezione vuota": (
            "abbiamo ricevuto la sua segnalazione relativa a una confezione trovata vuota o quasi vuota. "
            "Capiamo il disagio e vogliamo risolvere subito la situazione."
        ),
    }
    detail = specific.get(category, (
        f"abbiamo ricevuto la sua segnalazione relativa a: {category}. "
        "Prendiamo questo tipo di segnalazioni con la massima priorità."
    ))
    return (
        "Gentile Cliente,\n\n"
        f"{detail}\n\n"
        "Il nostro team qualità ha già preso in carico il suo caso e avvierà le verifiche necessarie "
        "sul lotto di produzione indicato. La invitiamo a conservare la confezione originale con "
        "il codice lotto e la data di scadenza ben visibili — potremmo richiedergliela per analisi.\n\n"
        "Come rimedio immediato, le offriamo il rimborso completo del prodotto acquistato "
        "e un buono acquisto da €15 come scusa per l'inconveniente. "
        "Il nostro team la contatterà all'email indicata entro 24 ore lavorative per "
        "concordare rimborso e modalità di ritiro della confezione.\n\n"
        "Cordiali saluti,\nTeam Qualità San Carlo"
    )
