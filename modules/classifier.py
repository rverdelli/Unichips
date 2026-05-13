"""
Complaint classification logic.
Replace classify_complaint() with an LLM call to upgrade to AI-powered classification.
"""

SIMPLE_KEYWORDS = [
    "bruciata", "bruciate", "scura", "scure", "verde", "verdi",
    "sbriciolata", "sbriciolate", "rotta", "rotte", "salata", "salate",
    "leggera", "leggere", "diversa", "diverse", "colore", "forma",
    "croccante", "croccantezza", "piccola", "piccole", "grande",
]

COMPLEX_KEYWORDS = [
    "corpo estraneo", "estraneo", "capello", "capelli", "insetto", "mosca",
    "vuota", "vuoto", "vuote", "muffa", "muffe", "ammuffita",
    "odore", "puzza", "puzzava", "contaminazione", "contaminato",
    "compromessa", "compromesso", "danneggiata", "danneggiato",
    "alterato", "alterata", "sicurezza", "avvelenamento", "intossicazione",
    "metallo", "plastica", "vetro", "sasso", "pietra", "filo",
]

PRIORITY_MAP = {
    "Corpo estraneo": "Alta",
    "Confezione vuota": "Alta",
    "Odore anomalo": "Alta",
    "Muffa / alterazione": "Alta",
    "Confezione danneggiata": "Media",
    "Gusto anomalo": "Media",
    "Patatina bruciata": "Bassa",
    "Patatina verde": "Bassa",
    "Prodotto sbriciolato": "Bassa",
    "Altro": "Bassa",
}


def classify_complaint(problem_category: str, description: str) -> dict:
    """
    Returns dict with keys: classification, status, priority, auto_response, ai_response
    Swap this function body with an LLM call for production.
    """
    text = (problem_category + " " + description).lower()

    is_complex = any(kw in text for kw in COMPLEX_KEYWORDS)
    is_simple = any(kw in text for kw in SIMPLE_KEYWORDS)

    if is_complex:
        classification = "complesso"
    elif is_simple:
        classification = "semplice"
    else:
        classification = "semplice"

    complex_categories = [
        "Corpo estraneo", "Confezione vuota", "Odore anomalo", "Muffa / alterazione"
    ]
    if problem_category in complex_categories:
        classification = "complesso"

    priority = PRIORITY_MAP.get(problem_category, "Normale")

    if classification == "semplice":
        status = "Chiuso automaticamente"
        auto_response = True
        ai_response = generate_auto_response(problem_category, description)
    else:
        status = "Aperto"
        auto_response = False
        ai_response = generate_complex_response(problem_category, description)

    return {
        "classification": classification,
        "status": status,
        "priority": priority,
        "auto_response": auto_response,
        "ai_response": ai_response,
    }


def generate_auto_response(category: str, description: str) -> str:
    responses = {
        "Patatina bruciata": (
            "Gentile Cliente,\n\n"
            "la ringraziamo per la sua segnalazione.\n\n"
            "In alcuni casi possono verificarsi leggere variazioni di colore nelle nostre patatine, "
            "dovute alle caratteristiche naturali delle patate e al processo di cottura ad alta temperatura. "
            "Si tratta di un fenomeno fisiologico che non compromette la sicurezza del prodotto.\n\n"
            "La sua segnalazione è stata comunque registrata e sarà utilizzata dal nostro team qualità "
            "per monitorare i processi produttivi.\n\n"
            "Cordiali saluti,\nTeam Qualità San Carlo"
        ),
        "Patatina verde": (
            "Gentile Cliente,\n\n"
            "la ringraziamo per la sua segnalazione.\n\n"
            "Le patatine di colore verde derivano da patate che hanno subito un leggero processo "
            "di inverdimento per esposizione alla luce. I nostri controlli qualità prevedono la "
            "selezione di queste patate, ma in rari casi qualcuna può passare inosservata.\n\n"
            "La sua segnalazione è stata registrata e contribuirà a migliorare i nostri standard.\n\n"
            "Cordiali saluti,\nTeam Qualità San Carlo"
        ),
        "Prodotto sbriciolato": (
            "Gentile Cliente,\n\n"
            "la ringraziamo per la sua segnalazione.\n\n"
            "Capisce bene che la fragilità delle patatine è intrinseca al prodotto. "
            "Durante il trasporto e la distribuzione possono verificarsi urti che causano la "
            "sbriciolatura di parte del contenuto. Stiamo costantemente lavorando per migliorare "
            "il packaging e ridurre al minimo questi inconvenienti.\n\n"
            "La sua segnalazione è stata registrata.\n\n"
            "Cordiali saluti,\nTeam Qualità San Carlo"
        ),
    }
    default = (
        "Gentile Cliente,\n\n"
        "la ringraziamo per la sua segnalazione.\n\n"
        "In alcuni casi possono verificarsi leggere differenze di colore, forma o croccantezza "
        "nei nostri prodotti, dovute alle caratteristiche naturali delle materie prime e al processo "
        "produttivo. Questo non compromette la qualità e la sicurezza del prodotto.\n\n"
        "La sua segnalazione è stata comunque registrata e sarà utilizzata per monitorare "
        "la qualità dei nostri prodotti.\n\n"
        "Cordiali saluti,\nTeam Qualità San Carlo"
    )
    return responses.get(category, default)


def generate_complex_response(category: str, description: str) -> str:
    return (
        "Gentile Cliente,\n\n"
        "la ringraziamo per la sua segnalazione.\n\n"
        f"Abbiamo registrato la sua segnalazione relativa a: **{category}**.\n\n"
        "Poiché il caso richiede una verifica più approfondita, il reclamo sarà preso in carico "
        "dal nostro team qualità che effettuerà le opportune verifiche.\n\n"
        "Riceverà un aggiornamento all'indirizzo email fornito entro 2-3 giorni lavorativi.\n\n"
        "La invitiamo a conservare la confezione e il prodotto, in quanto potrebbe essere "
        "necessario procedere con ulteriori analisi.\n\n"
        "Cordiali saluti,\nTeam Qualità San Carlo"
    )
