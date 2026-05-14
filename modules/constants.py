"""
Single source of truth for domain constants shared across modules.
"""

PRODUCTS = [
    "Più Gusto Vivace",
    "Più Gusto Lime e Pepe Rosa",
    "Più Gusto Porchetta",
    "Più Gusto Tartufo",
    "Classica",
    "Rustica",
    "Veggy Good",
    "Pop Corn San Carlo",
    "Wacko's",
    "Highlander",
]

CATEGORIES = [
    "Patatina bruciata",
    "Patatina verde",
    "Prodotto sbriciolato",
    "Gusto anomalo",
    "Corpo estraneo",
    "Confezione vuota",
    "Confezione danneggiata",
    "Odore anomalo",
    "Muffa / alterazione",
    "Altro",
]

CHANNELS = ["chatbot", "email", "telefono", "social"]

STATUSES = [
    "Aperto",
    "In lavorazione",
    "In attesa cliente",
    "Chiuso",
    "Chiuso automaticamente",
]

PRIORITIES = ["Alta", "Media", "Bassa"]

COMPLEX_CATEGORIES = frozenset({
    "Corpo estraneo",
    "Confezione vuota",
    "Odore anomalo",
    "Muffa / alterazione",
})

PRIORITY_MAP = {
    "Corpo estraneo": "Alta",
    "Confezione vuota": "Alta",
    "Odore anomalo": "Alta",
    "Muffa / alterazione": "Alta",
    "Confezione danneggiata": "Media",
    "Gusto anomalo": "Media",
    "Patatina bruciata": "Media",
    "Patatina verde": "Media",
    "Prodotto sbriciolato": "Media",
    "Altro": "Media",
}

COMPLAINT_INTENT_KEYWORDS = frozenset({
    "reclamo", "segnalazione", "problema", "rotto", "bruciata",
    "corpo estraneo", "vuota", "muffa", "odore", "segnalare",
    "reclami", "lamentela", "difetto", "sbriciolata", "verde",
})

REQUIRED_COMPLAINT_FIELDS = [
    "name", "email", "product", "lot_code", "description"
]

FIELD_LABELS = {
    "name": "Nome e cognome",
    "email": "Email di contatto",
    "product": "Prodotto acquistato",
    "problem_category": "Tipo di problema",
    "lot_code": "Codice lotto",
    "description": "Descrizione dell'accaduto",
    "expiry_date": "Data di scadenza",
    "purchase_location": "Punto vendita",
}

FIELD_PROMPTS = {
    "name": "Puoi dirmi il tuo **nome e cognome**?",
    "email": "Qual è il tuo **indirizzo email** di contatto?",
    "product": "Qual è il **prodotto** che hai acquistato? (es. Più Gusto Classica, Veggy Good, ecc.)",
    "problem_category": "Che tipo di **problema** hai riscontrato?",
    "lot_code": (
        "Hai il **codice lotto**? Lo trovi sul retro o sul bordo della confezione, "
        "vicino alla data di scadenza. Il formato è **LT seguito da 5 cifre** (es. `LT12345`)."
    ),
    "description": "Puoi descrivermi brevemente **cosa è successo**?",
}

# Columns allowed in UPDATE queries — prevent injection via update_complaint()
COMPLAINT_UPDATABLE_COLUMNS = frozenset({
    "status", "priority", "ai_response", "closed_at",
    "customer_name", "customer_email", "product", "problem_category",
    "description", "lot_code", "expiry_date", "purchase_location",
    "classification", "auto_response",
})
