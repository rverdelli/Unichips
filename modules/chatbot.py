"""
Chatbot conversation logic (state machine).
Replace process_message() with LLM integration for production.
"""
from modules.classifier import classify_complaint
from modules.database import save_complaint

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


def extract_info_from_text(text, collected):
    """
    Naive extraction — replace with NLP/LLM for production.
    Tries to detect email, lot codes, etc.
    """
    import re
    updated = dict(collected)

    # Email
    email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
    if email_match and not updated.get("email"):
        updated["email"] = email_match.group(0)

    # Lot code (alphanumeric 6-12 chars starting with L or digit)
    lot_match = re.search(r"\b[Ll][0-9A-Za-z]{4,11}\b|\b\d{2}[A-Za-z]\d{2,8}\b", text)
    if lot_match and not updated.get("lot_code"):
        updated["lot_code"] = lot_match.group(0).upper()

    # Product name detection
    if not updated.get("product"):
        text_lower = text.lower()
        for p in PRODUCTS:
            if p.lower() in text_lower:
                updated["product"] = p
                break

    # Category detection
    if not updated.get("problem_category"):
        text_lower = text.lower()
        cat_keywords = {
            "Patatina bruciata": ["bruciata", "bruciato", "bruciature", "nera", "scura"],
            "Patatina verde": ["verde", "verdi"],
            "Prodotto sbriciolato": ["sbriciolata", "sbriciolato", "rotta", "rotto", "frantumata"],
            "Gusto anomalo": ["gusto strano", "sapore strano", "sapore anomalo", "non sapeva"],
            "Corpo estraneo": ["corpo estraneo", "estraneo", "capello", "insetto", "mosca", "plastica", "metallo", "vetro", "sasso"],
            "Confezione vuota": ["vuota", "vuoto", "aperta", "aperto"],
            "Confezione danneggiata": ["danneggiata", "danneggiato", "busta rotta", "confezione rotta"],
            "Odore anomalo": ["odore", "puzza", "puzzava", "cattivo odore"],
            "Muffa / alterazione": ["muffa", "muffe", "ammuffita", "alterata"],
        }
        for cat, kws in cat_keywords.items():
            if any(kw in text_lower for kw in kws):
                updated["problem_category"] = cat
                break

    return updated


def process_message(user_text, state, waiting_for_field=None):
    """
    Main chatbot logic. Returns (bot_reply, updated_state, suggestions).
    """
    phase = state["phase"]
    collected = state.get("collected", {})
    suggestions = []

    # --- WELCOME ---
    if phase == "welcome":
        text_lower = user_text.lower()
        if "reclamo" in text_lower or "segnalazione" in text_lower or "problema" in text_lower:
            state["phase"] = "collecting"
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
            state["waiting_for"] = "name"

        elif "lotto" in text_lower or "confezione" in text_lower:
            reply = (
                "Il **codice lotto** si trova normalmente sul **retro o sul bordo della confezione**, "
                "vicino alla data di scadenza. È una sequenza alfanumerica, ad esempio: `L23A45B` oppure `23A456`.\n\n"
                "Hai bisogno di altro?"
            )
            suggestions = ["Voglio sottoporre un reclamo", "Avete prodotti senza glutine?"]

        elif "glutine" in text_lower or "senza glutine" in text_lower or "celiaci" in text_lower:
            reply = (
                "Alcuni prodotti San Carlo possono essere **privi di glutine**, come alcune varianti della linea Veggy Good. "
                "Ti invitiamo sempre a verificare l'etichetta del prodotto acquistato, "
                "dove sono riportate tutte le informazioni sugli allergeni.\n\n"
                "Per una lista aggiornata dei prodotti senza glutine, ti consigliamo di consultare "
                "il sito ufficiale San Carlo o contattare il nostro servizio clienti.\n\n"
                "Posso aiutarti con altro?"
            )
            suggestions = ["Voglio sottoporre un reclamo", "Dove trovo il lotto sulla confezione?"]

        else:
            reply = (
                "Ciao! Sono qui per aiutarti. Puoi chiedermi informazioni sui prodotti "
                "o aprire una segnalazione."
            )
            suggestions = [
                "Voglio sottoporre un reclamo",
                "Dove trovo il lotto sulla confezione?",
                "Avete prodotti senza glutine?",
            ]

        return reply, state, suggestions

    # --- COLLECTING INFO ---
    if phase == "collecting":
        # Try to extract info from what the user wrote
        collected = extract_info_from_text(user_text, collected)

        # If we were waiting for a specific field, assign the answer
        wf = state.get("waiting_for")
        if wf and not collected.get(wf):
            collected[wf] = user_text.strip()

        state["collected"] = collected
        missing = get_missing_fields(collected)

        if not missing:
            # All mandatory info collected — classify and save
            result = classify_complaint(
                collected.get("problem_category", ""),
                collected.get("description", ""),
            )
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
                    "In alcuni casi possono verificarsi leggere variazioni di colore o croccantezza "
                    "dovute alle caratteristiche naturali delle patate e al processo di cottura. "
                    "La tua segnalazione è stata **registrata** e sarà utilizzata per monitorare "
                    "la qualità dei nostri prodotti.\n\n"
                    "Riceverai una email di conferma all'indirizzo indicato."
                )
            else:
                reply = (
                    f"✅ **Segnalazione #{complaint_id} registrata.**\n\n"
                    f"Riepilogo informazioni ricevute:\n{summary}\n\n"
                    "---\n"
                    "Poiché il caso richiede una verifica più approfondita, il reclamo sarà "
                    "**preso in carico dal nostro team qualità**. "
                    "Riceverai un aggiornamento all'indirizzo email fornito entro 2-3 giorni lavorativi.\n\n"
                    "Ti invitiamo a conservare la confezione."
                )
            suggestions = ["Grazie!", "Aprire un altro reclamo"]

        else:
            # Ask for next missing field
            next_field = missing[0]
            state["waiting_for"] = next_field

            already = [f for f in REQUIRED_FIELDS if collected.get(f)]
            if already:
                summary = build_summary(collected)
                reply = (
                    f"Grazie! Ho già:\n{summary}\n\n"
                    f"Mi manca ancora: {FIELD_PROMPTS[next_field]}"
                )
            else:
                reply = FIELD_PROMPTS[next_field]

        return reply, state, suggestions

    # --- DONE ---
    if phase == "done":
        text_lower = user_text.lower()
        if "altro" in text_lower or "nuovo" in text_lower or "aprire" in text_lower:
            new_state = init_state()
            new_state["phase"] = "collecting"
            new_state["waiting_for"] = "name"
            reply = (
                "Certo! Apriamo una nuova segnalazione. "
                "Puoi dirmi il tuo **nome e cognome**?"
            )
            return reply, new_state, []
        else:
            reply = (
                "Grazie per aver contattato San Carlo! "
                "Se hai bisogno di altro non esitare a scrivermi. 😊"
            )
            return reply, state, ["Aprire un altro reclamo"]

    return "Come posso aiutarti?", state, suggestions
