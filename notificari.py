import os
import ast
import json
import urllib.request
import requests
from dotenv import load_dotenv

try:
    import streamlit as st
    for _k in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "RESEND_API_KEY", "RESEND_FROM_EMAIL"]:
        if _k in st.secrets and not os.environ.get(_k):
            os.environ[_k] = str(st.secrets[_k])
except Exception:
    pass

load_dotenv()


def _get_secret(key, default=""):
    val = os.getenv(key, "").strip()
    if not val:
        try:
            import streamlit as st
            val = str(st.secrets.get(key, "")).strip()
        except Exception:
            pass
    return val or default


def _get_bot_token():
    return _get_secret("TELEGRAM_BOT_TOKEN", "")


def _curata_md(text):
    if not text:
        return ""
    return str(text).replace("_", "-").replace("*", "").replace("`", "'")


def formateaza_lista_sarcini(sarcini_raw, separator="\n"):
    """Transformă atât o listă Python, cât și un text serializat cu apostrofuri în bullet-uri curate."""
    if not sarcini_raw:
        return "• Fără sarcini urgente"
    if isinstance(sarcini_raw, (list, tuple)):
        items = [str(x).strip() for x in sarcini_raw if str(x).strip()]
    else:
        txt = str(sarcini_raw).strip()
        if (txt.startswith("[") and txt.endswith("]")) or ("', '" in txt) or ('", "' in txt):
            try:
                parsed = ast.literal_eval(txt if txt.startswith("[") else f"[{txt}]")
                if isinstance(parsed, (list, tuple)):
                    items = [str(x).strip() for x in parsed if str(x).strip()]
                else:
                    items = [txt]
            except Exception:
                items = [p.strip().strip("'\"") for p in txt.strip("[]").split("', '") if p.strip()]
        else:
            items = [line.lstrip("•-* ").strip() for line in txt.splitlines() if line.strip()]
    if not items:
        return "• Fără sarcini urgente"
    return separator.join(f"• {it}" for it in items)


def trimite_notificare_telegram(numar_dosar, client, institutie, analiza, chat_id_destinatar=None):
    token = _get_bot_token()
    chat_id = str(chat_id_destinatar or "").strip()

    if not token or not chat_id:
        print(f"[Telegram] Lipsește token-ul sau Chat ID-ul destinatarului pentru dosarul {numar_dosar}.")
        return False

    prioritate = str(analiza.get("prioritate", "IMPORTANT")).upper()
    emoji_prio = "🔴" if prioritate == "URGENT" else ("🟡" if prioritate == "IMPORTANT" else "⚪")
    titlu_prio = "ALERTĂ URGENTĂ" if prioritate == "URGENT" else ("ALERTĂ IMPORTANTĂ" if prioritate == "IMPORTANT" else "ACTUALIZARE DOSAR")

    tip_solutie = _curata_md(analiza.get("tip_solutie", "Nespecificat"))
    noul_termen = _curata_md(analiza.get("noul_termen", "Nespecificat"))
    cale_atac = _curata_md(analiza.get("cale_atac", "Nu este cazul la acest moment"))
    sarcini_curate = _curata_md(formateaza_lista_sarcini(analiza.get("sarcini_avocat"), separator="\n"))
    mesaj_client = _curata_md(analiza.get("mesaj_client", ""))

    mesaj = (
        f"{emoji_prio} *ERRATA • {titlu_prio}*\n"
        f"⚖️ *Dosar:* {_curata_md(numar_dosar)}\n"
        f"👤 *Client:* {_curata_md(client) or 'Nespecificat'}\n"
        f"🏛️ *Instanță:* {_curata_md(institutie)}\n\n"
        f"📌 *Soluție:* {tip_solutie}\n"
        f"📅 *Următorul termen:* {noul_termen}\n"
        f"⏳ *Cale atac / Termen legal:* {cale_atac}\n\n"
        f"📝 *Sarcini procedurale:*\n{sarcini_curate}\n\n"
        f"💬 *Draft mesaj client (WhatsApp):*\n"
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
        payload.pop("parse_mode", None)
        raspuns2 = requests.post(url, json=payload, timeout=10)
        return bool(raspuns2.json().get("ok"))
    except Exception as e:
        print(f"[Telegram] Eroare conexiune: {e}")
        return False


def trimite_notificare_email(email_destinatar: str, numar_dosar: str, nume_client: str, institutie: str, analiza: dict) -> bool:
    api_key = _get_secret("RESEND_API_KEY", "")
    from_addr = _get_secret("RESEND_FROM_EMAIL", "Errata <alerte@errata.ro>")
    if not api_key or not email_destinatar or "@" not in email_destinatar:
        return False

    prioritate = str(analiza.get("prioritate", "IMPORTANT")).upper()
    if prioritate == "URGENT":
        badge_bg, badge_fg, badge_txt = "#FEF2F2", "#DC2626", "URGENT • ACȚIUNE IMEDIATĂ"
    elif prioritate == "ISTORIC":
        badge_bg, badge_fg, badge_txt = "#F1F5F9", "#475569", "ADMINISTRATIV / ISTORIC"
    else:
        badge_bg, badge_fg, badge_txt = "#FFFBEB", "#B45309", "IMPORTANT • PLANIFICARE"

    cale_atac = analiza.get("cale_atac") or "Fără cale de atac incidentă la acest moment"
    sarcini_html = formateaza_lista_sarcini(analiza.get("sarcini_avocat"), separator="<br/>")
    mesaj_client_html = str(analiza.get("mesaj_client", "")).replace("\n", "<br/>")

    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 640px; margin: 0 auto; border: 1px solid #E2E8F0; border-radius: 14px; overflow: hidden; background: #FFFFFF;">
        <div style="background: #0F172A; color: #FFFFFF; padding: 24px 28px; border-bottom: 3px solid #C5A059;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 13px; text-transform: uppercase; letter-spacing: 0.12em; color: #E2C792; font-weight: 700;">ERRATA • ASISTENT JURIDIC</span>
            </div>
            <h2 style="margin: 10px 0 4px 0; font-size: 22px; color: #FFFFFF; letter-spacing: -0.02em;">Dosar {numar_dosar}</h2>
            <p style="margin: 0; font-size: 13px; color: #94A3B8;">{institutie} {('• Client: <strong style="color:#F8FAFC;">' + nume_client + '</strong>') if nume_client else ''}</p>
        </div>

        <div style="padding: 26px 28px; color: #1E293B;">
            <div style="margin-bottom: 18px;">
                <span style="display: inline-block; background: {badge_bg}; color: {badge_fg}; font-size: 11px; font-weight: 700; letter-spacing: 0.06em; padding: 5px 12px; border-radius: 20px; border: 1px solid {badge_fg}33;">
                    {badge_txt}
                </span>
            </div>

            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 14px;">
                <tr>
                    <td style="padding: 8px 0; color: #64748B; width: 170px;"><strong>Soluție / Eveniment:</strong></td>
                    <td style="padding: 8px 0; color: #0F172A; font-weight: 700;">{analiza.get('tip_solutie', '-')}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #64748B;"><strong>Următorul termen:</strong></td>
                    <td style="padding: 8px 0; color: #0F172A; font-weight: 600;">{analiza.get('noul_termen', 'Fără termen stabilit')}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #64748B;"><strong>Cale de atac / Termen:</strong></td>
                    <td style="padding: 8px 0; color: #991B1B; font-weight: 600;">{cale_atac}</td>
                </tr>
            </table>

            <div style="background: #FAF8F5; border-left: 4px solid #C5A059; padding: 15px 18px; border-radius: 0 10px 10px 0; margin-bottom: 18px;">
                <strong style="color: #0F172A; font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em;">📌 Evaluare Procedurală & Sarcini Cabinet</strong><br/>
                <span style="font-size: 14px; color: #334155; line-height: 1.55; display: block; margin-top: 6px;">{sarcini_html}</span>
            </div>

            <div style="background: #F8FAFC; border-left: 4px solid #0F172A; padding: 15px 18px; border-radius: 0 10px 10px 0;">
                <strong style="color: #0F172A; font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em;">💬 Notificare Client (Gata de trimis)</strong><br/>
                <span style="font-size: 14px; color: #334155; line-height: 1.55; display: block; margin-top: 6px;">{mesaj_client_html}</span>
            </div>

            <div style="margin-top: 24px; text-align: center;">
                <a href="https://app.errata.ro" style="display: inline-block; background: #0F172A; color: #E2C792; text-decoration: none; font-weight: 600; font-size: 13px; padding: 11px 22px; border-radius: 8px;">
                    Deschide Dosarul în Errata →
                </a>
            </div>
        </div>

        <div style="background: #F1F5F9; padding: 14px 28px; font-size: 12px; color: #64748B; text-align: center; border-top: 1px solid #E2E8F0;">
            <strong>Errata</strong> • Securitate. Integritate. Rapiditate. | <a href="https://errata.ro" style="color: #0F172A; text-decoration: none;">errata.ro</a>
        </div>
    </div>
    """

    subiect_prefix = "🔴 URGENT" if prioritate == "URGENT" else "⚖️"
    payload = json.dumps({
        "from": from_addr,
        "to": [email_destinatar.strip()],
        "subject": f"{subiect_prefix} Dosar {numar_dosar} — {analiza.get('tip_solutie', 'Actualizare Portal Just')}",
        "html": html_body
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ErrataLegal/1.0"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        print(f"[Resend] Eroare trimitere email: {e}")
        return False


def trimite_digest_matinal(email_destinatar: str, nume_firma: str, lista_actualizari: list) -> bool:
    """Trimite briefing-ul zilnic consolidat (07:30) pentru toate evenimentele cabinetului."""
    api_key = _get_secret("RESEND_API_KEY", "")
    from_addr = _get_secret("RESEND_FROM_EMAIL", "Errata <alerte@errata.ro>")
    if not api_key or not email_destinatar or "@" not in email_destinatar or not lista_actualizari:
        return False

    randuri_html = ""
    for item in lista_actualizari:
        prio = str(item.get("prioritate", "IMPORTANT")).upper()
        culoare = "#DC2626" if prio == "URGENT" else ("#B45309" if prio == "IMPORTANT" else "#64748B")
        sarcini_item = formateaza_lista_sarcini(item.get("sarcini_avocat"), separator="<br/>")
        randuri_html += f"""
        <div style="border: 1px solid #E2E8F0; border-left: 4px solid {culoare}; border-radius: 8px; padding: 14px 16px; margin-bottom: 12px;">
            <div style="font-size: 12px; font-weight: 700; color: {culoare};">{prio} • {item.get('numar_dosar', '')} ({item.get('institutie', '')})</div>
            <div style="font-size: 14px; font-weight: 700; color: #0F172A; margin: 4px 0;">{item.get('tip_solutie', '')}</div>
            <div style="font-size: 13px; color: #475569;">Termen: <strong>{item.get('noul_termen', '-')}</strong> | Client: {item.get('nume_client', '-')}</div>
            <div style="font-size: 13px; color: #334155; margin-top: 6px;">{sarcini_item}</div>
        </div>
        """

    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 640px; margin: 0 auto; border: 1px solid #E2E8F0; border-radius: 14px; overflow: hidden;">
        <div style="background: #0F172A; color: #FFFFFF; padding: 22px 26px; border-bottom: 3px solid #C5A059;">
            <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em; color: #E2C792; font-weight: 700;">ERRATA • BRIEFING PROCEDURAL ZILNIC</div>
            <h2 style="margin: 6px 0 0 0; font-size: 20px;">Sinteză Cabinet — {nume_firma}</h2>
        </div>
        <div style="padding: 24px 26px; background: #FFFFFF;">
            <p style="font-size: 14px; color: #334155; margin-top: 0;">Aveți <strong>{len(lista_actualizari)}</strong> actualizări procedurale detectate în portofoliu:</p>
            {randuri_html}
        </div>
    </div>
    """

    payload = json.dumps({
        "from": from_addr,
        "to": [email_destinatar.strip()],
        "subject": f"📋 Errata Briefing — {len(lista_actualizari)} actualizări în portofoliu ({nume_firma})",
        "html": html_body
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ErrataLegal/1.0"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False
