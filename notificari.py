import os
try:
    import streamlit as st
    for k, v in st.secrets.items():
        if isinstance(v, str) and k not in os.environ:
            os.environ[k] = v
except Exception:
    pass

import os
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def trimite_notificare_telegram(numar_dosar, client, institutie, analiza):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram] Nu sunt setate TELEGRAM_BOT_TOKEN sau TELEGRAM_CHAT_ID in .env.")
        return False

    tip_solutie = analiza.get("tip_solutie", "Nespecificat")
    noul_termen = analiza.get("noul_termen", "Nespecificat")
    cale_atac = analiza.get("cale_atac", "Nespecificat")
    sarcini = analiza.get("sarcini_avocat", "Fara sarcini urgente")
    mesaj_client = analiza.get("mesaj_client", "")

    mesaj = (
        f"⚖️ *ACTUALIZARE DOSAR: {numar_dosar}*\n"
        f"👤 *Client:* {client or 'Nespecificat'}\n"
        f"🏛️ *Instanță:* {institutie}\n\n"
        f"📌 *Soluție:* {tip_solutie}\n"
        f"📅 *Noul termen / pronunțare:* {noul_termen}\n"
        f"⚖️ *Cale atac:* {cale_atac}\n\n"
        f"📝 *Sarcini avocat:*\n{sarcini}\n\n"
        f"💬 *Mesaj pentru client (draft WhatsApp):*\n"
        f"_{mesaj_client}_\n"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mesaj,
        "parse_mode": "Markdown"
    }

    try:
        raspuns = requests.post(url, json=payload, timeout=10)
        rezultat = raspuns.json()
        if rezultat.get("ok"):
            print("  [Telegram] Alerta a fost trimisă cu succes pe telefon!")
            return True
        else:
            print(f"  [Telegram] Eroare API Telegram: {rezultat.get('description')}")
            return False
    except Exception as e:
        print(f"  [Telegram] Eroare conexiune: {e}")
        return False

if __name__ == "__main__":
    # Test izolat pentru verificare conexiune
    print("Testare trimitere mesaj pe Telegram...")
    analiza_test = {
        "tip_solutie": "Amânare pronunțare",
        "noul_termen": "20.06.2024",
        "cale_atac": "N/A",
        "sarcini_avocat": "Verificare portal pe 20 iunie după ora 14:00.",
        "mesaj_client": "Bună ziua! Instanța a stabilit amânarea pronunțării pentru data de 20 iunie 2024."
    }
    trimite_notificare_telegram("1234/2/2024", "David Popescu", "Curtea de Apel BUCUREȘTI", analiza_test)