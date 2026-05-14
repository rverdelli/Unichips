"""
Generates ~1000 mock complaints for the San Carlo demo.
Run: python init_data.py
"""
import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path

try:
    from faker import Faker
    fake = Faker("it_IT")
except ImportError:
    print("Installing faker...")
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "faker"])
    from faker import Faker
    fake = Faker("it_IT")

from modules.database import init_db, DB_PATH
from modules.constants import PRODUCTS, CATEGORIES, CHANNELS, COMPLEX_CATEGORIES, PRIORITY_MAP

CATEGORY_WEIGHTS = [20, 15, 18, 12, 8, 5, 7, 6, 4, 5]

STATUSES_SIMPLE = ["Chiuso automaticamente"]
STATUSES_COMPLEX = ["Aperto", "In lavorazione", "In attesa cliente", "Chiuso"]
STATUS_WEIGHTS_COMPLEX = [30, 25, 15, 30]


DESCRIPTIONS = {
    "Patatina bruciata": [
        "Ho trovato alcune patatine completamente bruciate nella confezione.",
        "Metà delle patatine erano bruciate e di colore nero.",
        "La confezione conteneva patatine molto scure, quasi carbonizzate.",
    ],
    "Patatina verde": [
        "Ho trovato diverse patatine di colore verde nella busta.",
        "Alcune chips avevano chiazze verdi molto evidenti.",
        "Tutta una parte della confezione era di patatine verdognole.",
    ],
    "Prodotto sbriciolato": [
        "Ho aperto la confezione e le patatine erano quasi tutte in polvere.",
        "Il prodotto era completamente sbriciolato, probabilmente per un urto durante il trasporto.",
        "La confezione sembrava intatta ma all'interno le patatine erano tutte rotte.",
    ],
    "Gusto anomalo": [
        "Il sapore era molto diverso dal solito, quasi amaro.",
        "Ho sentito un gusto strano, non riconducibile al normale sapore del prodotto.",
        "Le patatine avevano un retrogusto metallico insolito.",
    ],
    "Corpo estraneo": [
        "Ho trovato un capello all'interno della confezione.",
        "C'era un piccolo frammento di plastica tra le patatine.",
        "Ho notato un corpo estraneo di colore scuro nelle patatine.",
    ],
    "Confezione vuota": [
        "Ho acquistato la confezione e al suo interno era completamente vuota.",
        "La busta era sigillata ma non conteneva nulla.",
        "Confezione vuota, probabilmente un difetto di confezionamento.",
    ],
    "Confezione danneggiata": [
        "La confezione era aperta quando l'ho acquistata.",
        "Il packaging era strappato lateralmente.",
        "La busta era danneggiata e il prodotto era esposto all'aria.",
    ],
    "Odore anomalo": [
        "Aprendo la confezione ho sentito un forte odore anomalo, non quello tipico del prodotto.",
        "Le patatine avevano un odore di rancido molto intenso.",
        "Odore strano e sgradevole appena aperta la busta.",
    ],
    "Muffa / alterazione": [
        "Ho trovato presenza di muffa sulle patatine.",
        "Il prodotto presentava evidenti segni di alterazione con chiazze bianche.",
        "Alcune patatine avevano muffa visibile in superficie.",
    ],
    "Altro": [
        "Il prodotto non corrispondeva alla descrizione sulla confezione.",
        "Peso netto inferiore a quanto dichiarato.",
        "Problema generico con il prodotto acquistato.",
    ],
}

AI_RESPONSES_SIMPLE = (
    "Gentile Cliente, la ringraziamo per la sua segnalazione. In alcuni casi possono verificarsi "
    "leggere variazioni di colore o croccantezza dovute alle caratteristiche naturali delle patate "
    "e al processo di cottura. La sua segnalazione è stata registrata. Cordiali saluti, Team Qualità San Carlo"
)

AI_RESPONSES_COMPLEX = (
    "Gentile Cliente, abbiamo registrato la sua segnalazione. Poiché il caso richiede una verifica "
    "più approfondita, il reclamo sarà preso in carico dal nostro team qualità. "
    "Riceverà un aggiornamento all'indirizzo email fornito entro 2-3 giorni lavorativi. "
    "Cordiali saluti, Team Qualità San Carlo"
)


def generate_lot_code():
    letters = "ABCDEFGHJKLMNPRSTUVWXYZ"
    return f"L{random.randint(10,99)}{random.choice(letters)}{random.randint(100,999)}"


def generate_expiry():
    d = datetime.now() + timedelta(days=random.randint(30, 400))
    return d.strftime("%m/%Y")


def generate_complaints(n=1000):
    now = datetime.now()
    complaints = []
    for _ in range(n):
        created_at = now - timedelta(
            days=random.randint(0, 730),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        category = random.choices(CATEGORIES, weights=CATEGORY_WEIGHTS)[0]
        is_complex = category in COMPLEX_CATEGORIES
        classification = "complesso" if is_complex else "semplice"

        if is_complex:
            status = random.choices(STATUSES_COMPLEX, weights=STATUS_WEIGHTS_COMPLEX)[0]
        else:
            status = "Chiuso automaticamente"

        closed_at = None
        if status in ("Chiuso", "Chiuso automaticamente"):
            delta_days = random.randint(0, 14) if is_complex else random.randint(0, 1)
            closed_at = (created_at + timedelta(days=delta_days)).strftime("%Y-%m-%d %H:%M:%S")

        descriptions = DESCRIPTIONS.get(category, DESCRIPTIONS["Altro"])
        description = random.choice(descriptions)

        complaints.append({
            "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "customer_name": fake.name(),
            "customer_email": fake.email(),
            "product": random.choice(PRODUCTS),
            "problem_category": category,
            "description": description,
            "lot_code": generate_lot_code(),
            "expiry_date": generate_expiry(),
            "purchase_location": random.choice([
                fake.city(), "Esselunga", "Conad", "Coop", "Carrefour",
                "Eurospin", "Lidl", "Pam", "Auchan", "Bennet", ""
            ]),
            "status": status,
            "priority": PRIORITY_MAP.get(category, "Normale"),
            "channel": random.choices(CHANNELS, weights=[40, 30, 20, 10])[0],
            "classification": classification,
            "auto_response": 0 if is_complex else 1,
            "ai_response": AI_RESPONSES_COMPLEX if is_complex else AI_RESPONSES_SIMPLE,
            "closed_at": closed_at,
            "has_photo": random.choices([0, 1], weights=[70, 30])[0],
        })
    return complaints


def main():
    print("Inizializzazione database...")
    init_db()

    conn = sqlite3.connect(str(DB_PATH))
    count = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]

    if count > 0:
        print(f"Database già popolato con {count} reclami. Skip.")
        conn.close()
        return

    print("Generazione 1000 reclami mock...")
    complaints = generate_complaints(1000)

    conn.executemany("""
        INSERT INTO complaints
        (created_at, customer_name, customer_email, product, problem_category,
         description, lot_code, expiry_date, purchase_location, status, priority,
         channel, classification, auto_response, ai_response, closed_at, has_photo)
        VALUES
        (:created_at, :customer_name, :customer_email, :product, :problem_category,
         :description, :lot_code, :expiry_date, :purchase_location, :status, :priority,
         :channel, :classification, :auto_response, :ai_response, :closed_at, :has_photo)
    """, complaints)
    conn.commit()
    conn.close()
    print(f"✓ {len(complaints)} reclami inseriti in {DB_PATH}")


if __name__ == "__main__":
    main()
