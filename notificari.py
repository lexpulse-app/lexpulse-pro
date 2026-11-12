import os
import requests
from dotenv import load_dotenv

try:
    import streamlit as st
    for _k in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]:
        if _k in st.secrets and not os.environ.get(_k):
            os.environ[_k] = str(st.secrets[_k])
except Exception:
    pass

load_dotenv()


def _get_bot_token():
    tok = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not tok:
        try:
            import streamlit as st
            tok = str(st.secrets.get("TELEGRAM_BOT_TOKEN", "")).strip()
        except Exception:
            pass
    return tok


def _curata_md(text):
    if not text:
        return ""
    return str(text).replace("_", "-").replace("*", "").replace("`", "'")


def trimite_notificare_telegram(numar_dosar, client, institutie, analiza, chat_id_destinatar=None):
    token = _get_bot_token()
    chat_id = str(chat_id_destinatar or "").strip()

    if not token or not chat_id:
        print(f"[Telegram] Lipseste token-ul sau Chat ID-ul destinatarului pentru dosarul {numar_dosar}.")
        return False

    tip_solutie = _curata_md(analiza.get("tip_solutie", "Nespecificat"))
    noul_termen = _curata_md(analiza.get("noul_termen", "Nespecificat"))
    cale_atac = _curata_md(analiza.get("cale_atac", "Nespecificat"))
    sarcini = _curata_md(analiza.get("sarcini_avocat", "Fără sarcini urgente"))
    mesaj_client = _curata_md(analiza.get("mesaj_client", ""))

    mesaj = (
        f"⚖️ *ACTUALIZARE DOSAR: {_curata_md(numar_dosar)}*\n"
        f"👤 *Client:* {_curata_md(client) or 'Nespecificat'}\n"
        f"🏛️ *Instanță:* {_curata_md(institutie)}\n\n"
        f"📌 *Soluție:* {tip_solutie}\n"
        f"📅 *Noul termen / pronunțare:* {noul_termen}\n"
        f"⚖️ *Cale atac:* {cale_atac}\n\n"
        f"📝 *Sarcini avocat:*\n{sarcini}\n\n"
        f"💬 *Mesaj pentru client (draft WhatsApp):*\n"
        f"{mesaj_client}\n"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mesaj,
        "parse_mode": "Markdown"
    }

    try:
        raspuns = requests.post(url, json=payload, timeout=10)
        rezultat = raspuns.json()
        if rezultat.get("ok"):
            return True
        # Fallback fara Markdown daca textul are simboluri speciale
        payload.pop("parse_mode", None)
        raspuns2 = requests.post(url, json=payload, timeout=10)
        return bool(raspuns2.json().get("ok"))
    except Exception as e:
        print(f"[Telegram] Eroare conexiune: {e}")
        return False
