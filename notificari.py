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


def trimite_notificare_email(email_destinatar: str, numar_dosar: str, nume_client: str, institutie: str, analiza: dict) -> bool:
    import os, urllib.request, json
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_addr = os.getenv("RESEND_FROM_EMAIL", "LexPulse Pro <onboarding@resend.dev>").strip()
    if not api_key or not email_destinatar or "@" not in email_destinatar:
        return False

    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 620px; margin: 0 auto; border: 1px solid #E2E8F0; border-radius: 12px; overflow: hidden;">
        <div style="background: #0F172A; color: #FFFFFF; padding: 20px 24px;">
            <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: #38BDF8; font-weight: 700;">LexPulse Pro • Alertă Procedurală</div>
            <h2 style="margin: 6px 0 0 0; font-size: 20px;">Dosar {numar_dosar}</h2>
            <p style="margin: 4px 0 0 0; font-size: 13px; color: #94A3B8;">{institutie} {('• Client: ' + nume_client) if nume_client else ''}</p>
        </div>
        <div style="padding: 24px; background: #FFFFFF; color: #1E293B;">
            <p style="margin: 0 0 12px 0;"><strong>Soluție / Tip eveniment:</strong> <span style="color: #DC2626; font-weight: 600;">{analiza.get('tip_solutie', '-')}</span></p>
            <p style="margin: 0 0 16px 0;"><strong>Următorul termen:</strong> {analiza.get('noul_termen', 'Fără termen stabilit')}</p>
            <div style="background: #FFFBEB; border-left: 4px solid #F59E0B; padding: 14px 16px; border-radius: 0 8px 8px 0; margin-bottom: 16px;">
                <strong style="color: #78350F;">📌 Evaluare Procedurală & Sarcini Avocat:</strong><br/>
                <span style="font-size: 14px; color: #78350F;">{analiza.get('sarcini_avocat', '')}</span>
            </div>
            <div style="background: #F8FAFC; border-left: 4px solid #3B82F6; padding: 14px 16px; border-radius: 0 8px 8px 0;">
                <strong style="color: #1E293B;">💬 Mesaj Pre-Generat pentru Client:</strong><br/>
                <span style="font-size: 14px; color: #334155;">{analiza.get('mesaj_client', '')}</span>
            </div>
        </div>
        <div style="background: #F1F5F9; padding: 12px 24px; font-size: 12px; color: #64748B; text-align: center;">
            Notificare generată automat de <strong>LexPulse Pro</strong>
        </div>
    </div>
    """

    payload = json.dumps({
        "from": from_addr,
        "to": [email_destinatar.strip()],
        "subject": f"⚖️ Dosar {numar_dosar} — {analiza.get('tip_solutie', 'Actualizare Portal Just')}",
        "html": html_body
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "LexPulsePro/1.0"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False
