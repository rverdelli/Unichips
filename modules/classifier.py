"""
Complaint processing: cluster assignment + classification + response generation.
process_complaint() is the single entry point called by chatbot.py.
Classification is derived from gravity: Alta → complesso, Media/Bassa → semplice.
"""
import logging

from modules.constants import PRIORITY_MAP

logger = logging.getLogger(__name__)

# Fallback mapping from old categories to cluster1/cluster2
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


def process_complaint(collected: dict, config: dict) -> dict:
    """
    Single entry point: assign cluster, derive classification from gravity, generate response.
    Returns: cluster1, cluster2, gravity, classification, status, auto_response, ai_response.
    """
    from modules import llm as llm_module

    clusters = config.get("clusters") or []

    if llm_module.is_configured(config) and clusters:
        try:
            result = llm_module.process_complaint_with_clusters(collected, clusters, config)
            if result.get("cluster1"):
                return result
        except Exception as e:
            logger.warning("LLM process_complaint failed, using fallback: %s", e)

    return _mock_process_complaint(collected, clusters)


def _mock_process_complaint(collected: dict, clusters: list) -> dict:
    """Keyword-based fallback: assign clusters then derive classification."""
    category = collected.get("problem_category", "Altro")
    cluster1, cluster2 = _CATEGORY_TO_CLUSTER.get(category, ("ORGANOLETTICO", "GUSTO NON GRADITO"))

    # Look up gravity from cluster table; fall back to PRIORITY_MAP
    gravity = None
    for c in clusters:
        if c.get("cluster1") == cluster1 and c.get("cluster2") == cluster2:
            gravity = c.get("gravity")
            break
    if gravity is None:
        gravity = PRIORITY_MAP.get(category, "Media")

    is_complex = gravity == "Alta"

    return {
        "cluster1":       cluster1,
        "cluster2":       cluster2,
        "gravity":        gravity,
        "priority":       gravity,
        "classification": "complesso" if is_complex else "semplice",
        "status":         "Aperto" if is_complex else "Chiuso automaticamente",
        "auto_response":  not is_complex,
        "ai_response":    _generate_complex_response(category) if is_complex
                          else _generate_auto_response(category),
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
        "e un buono acquisto da €5 come scusa per l'inconveniente. "
        "Il nostro team la contatterà all'email indicata entro 24 ore lavorative per "
        "concordare rimborso e modalità di ritiro della confezione.\n\n"
        "Cordiali saluti,\nTeam Qualità San Carlo"
    )
