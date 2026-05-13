# San Carlo — Chatbot Customer Care Demo

Demo completa per la presentazione del chatbot customer care San Carlo / Unichips.

## Avvio rapido (Windows)

**Doppio click su `START_DEMO.bat`**

Il file batch:
1. Verifica Python installato
2. Crea virtual environment `.venv`
3. Installa dipendenze da `requirements.txt`
4. Genera ~1000 reclami mock (solo al primo avvio)
5. Lancia le due app Streamlit
6. Apre il browser sulle URL corrette

### URL

| App | URL |
|-----|-----|
| Sito pubblico + CarloBot | http://localhost:8501 |
| Dashboard Admin | http://localhost:8502 |

---

## Avvio manuale (Linux / Mac)

```bash
# Crea e attiva venv
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Installa dipendenze
pip install -r requirements.txt

# Genera dati mock
python init_data.py

# Avvia app pubblica (terminale 1)
streamlit run public_app.py --server.port 8501

# Avvia admin (terminale 2)
streamlit run admin_app.py --server.port 8502
```

---

## Struttura progetto

```
Unichips/
├── START_DEMO.bat          # Avvio Windows con doppio click
├── requirements.txt
├── init_data.py            # Generatore dati mock (~1000 reclami)
├── public_app.py           # Sito San Carlo + chatbot CarloBot
├── admin_app.py            # Dashboard interna gestione reclami
├── modules/
│   ├── database.py         # Layer dati SQLite (sostituibile con API)
│   ├── classifier.py       # Classificazione reclami (sostituibile con LLM)
│   └── chatbot.py          # Logica conversazionale (sostituibile con LLM)
└── data/
    ├── complaints.db       # SQLite database (generato automaticamente)
    └── chatbot_config.json # Configurazione chatbot (generato automaticamente)
```

---

## Funzionalità

### Sito pubblico (porta 8501)
- Replica visiva del sito San Carlo
- Chatbot CarloBot con pulsante floating
- Flusso reclamo guidato step-by-step
- Classificazione automatica (semplice / complesso)
- Salvataggio reclamo nel database

### Dashboard Admin (porta 8502)
- KPI overview in tempo reale
- Tabella reclami con filtri e ricerca
- Dettaglio reclamo con editor risposta AI
- Timeline e gestione stato
- Analisi con grafici interattivi Plotly
- Configurazione chatbot (common knowledge + regole)

---

## Upgrade produzione

Il codice è strutturato per facilitare la sostituzione dei componenti mock:

| File | Mock attuale | Upgrade |
|------|-------------|---------|
| `modules/classifier.py` → `classify_complaint()` | Keyword matching | Chiamata LLM (Claude, GPT) |
| `modules/chatbot.py` → `process_message()` | State machine | LLM con function calling |
| `modules/database.py` → `save_complaint()` | SQLite | API REST / PostgreSQL |

---

## Requisiti

- Python 3.9+
- Connessione internet per installazione pacchetti (solo primo avvio)
