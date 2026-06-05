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
    "status", "priority", "gravity", "ai_response", "closed_at",
    "customer_name", "customer_email", "product", "problem_category",
    "description", "lot_code", "expiry_date", "purchase_location",
    "classification", "auto_response", "cluster1", "cluster2",
    "conversation_history",
})

# Default cluster/gravity table — mirrors the San Carlo quality defect hierarchy
DEFAULT_CLUSTERS = [
    # ── ORGANOLETTICO ────────────────────────────────────────────────────────
    {"cluster1": "ORGANOLETTICO", "cluster2": "AROMA DIVERSO DA QUANTO INDICATO SUL PACK",        "gravity": "Alta",  "example": "es: lime e pepe rosa con aroma pomodoro (allergeni e inganno al consumatore)"},
    {"cluster1": "ORGANOLETTICO", "cluster2": "AROMA SU PRODOTTO NON AROMATIZZATO",               "gravity": "Alta",  "example": "es: classica con aromatizzazione (allergeni e inganno al consumatore)"},
    {"cluster1": "ORGANOLETTICO", "cluster2": "CATTIVO SAPORE / ODORE / CONSISTENZA DA PACK-GADGET","gravity": "Media", "example": "prodotto non croccante o sapore di vecchio imputabile al packaging; odore/sapore di plastica o chimico"},
    {"cluster1": "ORGANOLETTICO", "cluster2": "DIFETTI DI CONSISTENZA",                           "gravity": "Bassa", "example": "es: duro, molli, fette bagnate per shock termici, centri molli, gommose"},
    {"cluster1": "ORGANOLETTICO", "cluster2": "DIFETTI VISIVI",                                   "gravity": "Media", "example": "es: bruciature/bruciate/troppo cotte, chips rosse, macchie, inverdimenti"},
    {"cluster1": "ORGANOLETTICO", "cluster2": "GUSTO ANOMALO",                                    "gravity": "Bassa", "example": "es: cattive, sgradevoli, rancide, odori sgradevoli, stantie, vecchie"},
    {"cluster1": "ORGANOLETTICO", "cluster2": "GUSTO NON GRADITO",                                "gravity": "Bassa", "example": "gusto diverso da un ipotetico precedente, sapore diverso dal solito - pareri generici"},
    {"cluster1": "ORGANOLETTICO", "cluster2": "MANCANZA / ECCESSO SALE",                          "gravity": "Bassa", "example": ""},
    {"cluster1": "ORGANOLETTICO", "cluster2": "MANCANZA AROMA",                                   "gravity": "Bassa", "example": "es: più gusto senza aromatizzazione"},
    {"cluster1": "ORGANOLETTICO", "cluster2": "POCO AROMA",                                       "gravity": "Bassa", "example": "es: più gusto poco aromatizzate"},
    {"cluster1": "ORGANOLETTICO", "cluster2": "ROTTURE/INTRINSECHE DI PRODOTTO",                  "gravity": "Bassa", "example": "tante rotture, tante briciole, parte centrale del crostino che si distacca"},
    # ── CORPO ESTRANEO ───────────────────────────────────────────────────────
    {"cluster1": "CORPO ESTRANEO", "cluster2": "GERMOGLI",                                        "gravity": "Media", "example": "germoglio di crescita"},
    {"cluster1": "CORPO ESTRANEO", "cluster2": "STOLONI/GERMOGLI",                                "gravity": "Alta",  "example": "stoloni/germogli di conformazione differente dal tipico germoglio (possibile danno al consumatore)"},
    {"cluster1": "CORPO ESTRANEO", "cluster2": "INSETTI/TRACCE DI ANIMALI",                       "gravity": "Alta",  "example": "es: escrementi di animali / blatte / formiche"},
    {"cluster1": "CORPO ESTRANEO", "cluster2": "LEGNO",                                           "gravity": "Alta",  "example": "es: da cassoni o da legno arrivato con carico patate"},
    {"cluster1": "CORPO ESTRANEO", "cluster2": "METALLO",                                         "gravity": "Alta",  "example": "corpi metallici vari comprese le monete"},
    {"cluster1": "CORPO ESTRANEO", "cluster2": "MORCHIA / CORPI CARBONIOSI / NON ESPANSI",        "gravity": "Alta",  "example": "morchia, corpi carboniosi, pellet non espanso e/o popped bruciato/carbonizzato"},
    {"cluster1": "CORPO ESTRANEO", "cluster2": "ORGANICO / VEGETALE",                             "gravity": "Media", "example": "es: patata intera senza muffa / agglomerato di fettine / porzione di baguette"},
    {"cluster1": "CORPO ESTRANEO", "cluster2": "PEZZI DI IMPIANTO DI QUALSIASI NATURA",           "gravity": "Alta",  "example": "pezzi di impianto metallica, plastica o altra derivanti dalla linea produttiva"},
    {"cluster1": "CORPO ESTRANEO", "cluster2": "PLASTICA",                                        "gravity": "Alta",  "example": "pezzi di sacchi da gadget/recupero; pezzi di plastica non derivanti da impianti"},
    {"cluster1": "CORPO ESTRANEO", "cluster2": "CAPELLI / PELI",                                  "gravity": "Alta",  "example": "capelli/peli"},
    {"cluster1": "CORPO ESTRANEO", "cluster2": "VARI",                                            "gravity": "Alta",  "example": "es: sasso, carta, corpi estranei non definibili, filamenti di materiale sconosciuto"},
    # ── DIFETTI DI PACKAGING ─────────────────────────────────────────────────
    {"cluster1": "DIFETTI DI PACKAGING", "cluster2": "CARTONE: ERRORI TIMBRATURA DIVERSI DA LOTTO E TMC", "gravity": "Media", "example": "CODICE / DESCRIZIONE / EAN ERRATI O ILLEGGIBILI; differenze tra confezione e cartone"},
    {"cluster1": "DIFETTI DI PACKAGING", "cluster2": "CARTONE: ERRORI TIMBRATURA LOTTO - TMC",    "gravity": "Alta",  "example": "mancanza timbratura lotto/TMC sul cartone o errata timbratura"},
    {"cluster1": "DIFETTI DI PACKAGING", "cluster2": "CARTONI CON CONFEZIONI MANCANTI",           "gravity": "Bassa", "example": ""},
    {"cluster1": "DIFETTI DI PACKAGING", "cluster2": "CARTONI VUOTI",                             "gravity": "Bassa", "example": ""},
    {"cluster1": "DIFETTI DI PACKAGING", "cluster2": "CONFEZIONE CON GIUNTA DI BOBINA",           "gravity": "Media", "example": ""},
    {"cluster1": "DIFETTI DI PACKAGING", "cluster2": "CONFEZIONE: ERRORI TIMBRATURA (LOTTO - TMC)","gravity": "Media", "example": "errore che non ha impatti legali (es: 1 mese in più/meno dello standard)"},
    {"cluster1": "DIFETTI DI PACKAGING", "cluster2": "CONFEZIONI: ASSENZA DI TIMBRATURA (LOTTO E TMC)", "gravity": "Alta", "example": "timbratura assente o illegibile"},
    {"cluster1": "DIFETTI DI PACKAGING", "cluster2": "DDT / ETICHETTA PALLET CON DATI TRACCIABILITÀ DIVERSI", "gravity": "Alta", "example": "errori di tracciabilità tra DDT e confezione"},
    {"cluster1": "DIFETTI DI PACKAGING", "cluster2": "DIFFICOLTÀ DI PACKAGING/CONFEZIONAMENTO",   "gravity": "Media", "example": "grissini rotti nelle monoporzioni; diverso numero di grissini; monoporzioni di difficile apertura"},
    {"cluster1": "DIFETTI DI PACKAGING", "cluster2": "FUORIUSCITA DI OLIO DALLE CONFEZIONI",      "gravity": "Bassa", "example": ""},
    {"cluster1": "DIFETTI DI PACKAGING", "cluster2": "GADGET ASSENTI",                            "gravity": "Bassa", "example": ""},
    {"cluster1": "DIFETTI DI PACKAGING", "cluster2": "PRODOTTO DIFFERENTE DA QUANTO INDICATO SUL PACKAGING", "gravity": "Media", "example": "es: rustica al posto di classica senza impatti di allergeni"},
    {"cluster1": "DIFETTI DI PACKAGING", "cluster2": "SALDATURE APERTE",                          "gravity": "Media", "example": "saldature longitudinali o orizzontali non correttamente saldate"},
    {"cluster1": "DIFETTI DI PACKAGING", "cluster2": "SOTTOPESO",                                 "gravity": "Alta",  "example": "confezione con poche sfoglie, confezione in sottopeso rispetto al nominale"},
    {"cluster1": "DIFETTI DI PACKAGING", "cluster2": "UTILIZZO PACK NON IN LINEA CON INGREDIENTI","gravity": "Alta",  "example": "es: incarti con lista ingredienti non aggiornati o errati"},
    # ── MICROBIOLOGICO ───────────────────────────────────────────────────────
    {"cluster1": "MICROBIOLOGICO", "cluster2": "MUFFA",                                           "gravity": "Alta",  "example": "pane, patata intera con muffa, agglomerati di fettine con muffa"},
    {"cluster1": "MICROBIOLOGICO", "cluster2": "FUORI SPECIFICA PER MICRO OUT.STD.",               "gravity": "Media", "example": "analisi da laboratorio esterno"},
    {"cluster1": "MICROBIOLOGICO", "cluster2": "FUORI SPECIFICA PER MICRO GRAVE",                 "gravity": "Alta",  "example": "parametri microbiologici che impattano sulla salubrità (es: patogeni)"},
    # ── CHIMICO ──────────────────────────────────────────────────────────────
    {"cluster1": "CHIMICO", "cluster2": "FUORI SPECIFICA PER CHIMICO OUT.STD.",                    "gravity": "Media", "example": "parametri chimici che non impattano sulla salubrità (es: perossidi, umidità > standard)"},
    {"cluster1": "CHIMICO", "cluster2": "FUORI SPECIFICA PER CHIMICO GRAVE",                       "gravity": "Alta",  "example": "parametri chimici che impattano sulla salubrità (es: fitofarmaci, antibiotici)"},
    # ── BIOLOGICO ────────────────────────────────────────────────────────────
    {"cluster1": "BIOLOGICO", "cluster2": "FUORI SPECIFICA PER FILTH TEST OUT.STD.",               "gravity": "Media", "example": ""},
]
