import os
import json
import hmac
import hashlib
import base64
import time as _time_mod
import urllib.parse
from datetime import datetime, timedelta

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import stripe

for k in ["ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "DATABASE_URL", "STRIPE_SECRET_KEY", "RESEND_API_KEY", "RESEND_FROM_EMAIL"]:
    if k in st.secrets and not os.environ.get(k):
        os.environ[k] = str(st.secrets[k])

import baza_date
import app
import export_pdf
import calendar_sync
import notificari

# Pictogramă oficială Errata (SVG Data URI pentru Favicon, PWA iOS/Android și UI)
ERRATA_ICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'>"
    "<rect width='512' height='512' rx='112' fill='#0F172A'/>"
    "<rect x='18' y='18' width='476' height='476' rx='98' fill='none' stroke='#C5A059' stroke-width='6' stroke-opacity='0.45'/>"
    "<text x='256' y='345' text-anchor='middle' font-family='Georgia, serif' font-weight='bold' font-size='290' fill='#E2C792'>E</text>"
    "<path d='M145 275 Q256 235 367 215' stroke='#C5A059' stroke-width='10' fill='none' stroke-linecap='round'/>"
    "<polygon points='145,275 128,312 162,312' fill='#E2C792'/>"
    "<polygon points='367,215 350,252 384,252' fill='#E2C792'/>"
    "</svg>"
)
ERRATA_ICON_DATA_URI = "data:image/svg+xml;utf8," + urllib.parse.quote(ERRATA_ICON_SVG)

st.set_page_config(
    page_title="Errata | Asistent Juridic & Monitorizare Dosare",
    page_icon=ERRATA_ICON_DATA_URI,
    layout="wide",
    initial_sidebar_state="auto"
)

# Injectare PWA Manifest, Apple Touch Icon & Auto-închidere Sidebar pe mobil
components.html(f"""
<script>
(function() {{
    const doc = window.parent.document;
    if (!doc.querySelector("link[rel='apple-touch-icon']")) {{
        const appleIcon = doc.createElement('link');
        appleIcon.rel = 'apple-touch-icon';
        appleIcon.href = "{ERRATA_ICON_DATA_URI}";
        doc.head.appendChild(appleIcon);
    }}
    if (!doc.querySelector("meta[name='apple-mobile-web-app-capable']")) {{
        const metaCap = doc.createElement('meta');
        metaCap.name = 'apple-mobile-web-app-capable';
        metaCap.content = 'yes';
        doc.head.appendChild(metaCap);

        const metaTitle = doc.createElement('meta');
        metaTitle.name = 'apple-mobile-web-app-title';
        metaTitle.content = 'Errata';
        doc.head.appendChild(metaTitle);

        const metaTheme = doc.createElement('meta');
        metaTheme.name = 'theme-color';
        metaTheme.content = '#0F172A';
        doc.head.appendChild(metaTheme);
    }}
    if (!doc.querySelector("link[rel='manifest']")) {{
        const manifest = {{
            name: "Errata — Asistent Juridic",
            short_name: "Errata",
            start_url: "/",
            display: "standalone",
            background_color: "#0F172A",
            theme_color: "#0F172A",
            icons: [{{ src: "{ERRATA_ICON_DATA_URI}", sizes: "512x512", type: "image/svg+xml" }}]
        }};
        const blob = new Blob([JSON.stringify(manifest)], {{type: 'application/json'}});
        const link = doc.createElement('link');
        link.rel = 'manifest';
        link.href = URL.createObjectURL(blob);
        doc.head.appendChild(link);
    }}

    if (!doc.body.dataset.errataMobileNav) {{
        doc.body.dataset.errataMobileNav = "1";
        doc.addEventListener('click', function(e) {{
            if (window.parent.innerWidth <= 768) {{
                const radioLabel = e.target.closest('section[data-testid="stSidebar"] div[role="radiogroup"] label');
                if (radioLabel) {{
                    setTimeout(function() {{
                        const closeBtn = doc.querySelector('section[data-testid="stSidebar"] button');
                        if (closeBtn) closeBtn.click();
                    }}, 180);
                }}
            }}
        }}, true);
    }}
}})();
</script>
""", height=0, width=0)


@st.cache_resource
def _init_db_once():
    baza_date.init_db()
    return True


_init_db_once()


# ----------------- PERSISTENȚĂ SESIUNE 30 ZILE -----------------
def _gen_session_token(user_dict: dict) -> str:
    secret = (os.getenv("DATABASE_URL") or "errata_secret_salt_2026").encode()
    exp = int(_time_mod.time()) + 30 * 86400
    raw_payload = json.dumps({
        "id": user_dict["id"],
        "email": user_dict["email"],
        "nume_firma": user_dict["nume_firma"],
        "exp": exp
    }, separators=(",", ":"))
    b64 = base64.urlsafe_b64encode(raw_payload.encode()).decode()
    sig = hmac.new(secret, b64.encode(), hashlib.sha256).hexdigest()[:24]
    return f"{b64}.{sig}"


def _verify_session_token(token: str):
    try:
        if not token or "." not in token:
            return None
        b64, sig = token.rsplit(".", 1)
        secret = (os.getenv("DATABASE_URL") or "errata_secret_salt_2026").encode()
        expected = hmac.new(secret, b64.encode(), hashlib.sha256).hexdigest()[:24]
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(b64.encode()).decode())
        if int(data.get("exp", 0)) < int(_time_mod.time()):
            return None
        return {"id": data["id"], "email": data["email"], "nume_firma": data["nume_firma"]}
    except Exception:
        return None


if "utilizator" not in st.session_state:
    st.session_state.utilizator = None

if not st.session_state.utilizator and "session" in st.query_params:
    restored_user = _verify_session_token(st.query_params["session"])
    if restored_user:
        st.session_state.utilizator = restored_user
        st.session_state.keep_logged_in = True


def deconectare():
    st.session_state.utilizator = None
    st.session_state.keep_logged_in = False
    st.session_state["force_logout_msg"] = True
    st.query_params.pop("session", None)
    st.rerun()


def formateaza_telefon_whatsapp(telefon_raw):
    if not telefon_raw:
        return ""
    curat = "".join(filter(str.isdigit, str(telefon_raw)))
    if curat.startswith("0") and len(curat) == 10:
        return "4" + curat
    return curat


def extrage_prioritate_alerta(row):
    sarcini = str(row.get("sarcini_avocat") or "")
    if sarcini.startswith("[URGENT]"):
        raw_s = sarcini.replace("[URGENT]", "", 1).strip()
        return "URGENT", notificari.formateaza_lista_sarcini(raw_s, separator="\n")
    if sarcini.startswith("[ISTORIC]"):
        raw_s = sarcini.replace("[ISTORIC]", "", 1).strip()
        return "ISTORIC", notificari.formateaza_lista_sarcini(raw_s, separator="\n")
    if sarcini.startswith("[IMPORTANT]"):
        raw_s = sarcini.replace("[IMPORTANT]", "", 1).strip()
        return "IMPORTANT", notificari.formateaza_lista_sarcini(raw_s, separator="\n")
    prio = app.clasifica_prioritate_fallback(str(row.get("tip_solutie") or ""), sarcini)
    return prio, notificari.formateaza_lista_sarcini(sarcini, separator="\n")


# ----------------- DESIGN SYSTEM ERRATA (BLEUMARIN & AURIU-ȘAMPANIE) -----------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Playfair+Display:wght@700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .stApp {
        background-color: #F8FAFC;
        overflow-x: hidden;
    }

    /* Ascunde elementele implicite Streamlit păstrând butonul >> de meniu */
    footer, #MainMenu, [data-testid="stToolbarActions"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="stElementToolbar"], .viewerBadge_container__1QSob {
        display: none !important;
        visibility: hidden !important;
    }
    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    .block-container {
        padding-top: 1.4rem !important;
        padding-bottom: 5rem !important;
        max-width: 1280px !important;
    }

    .exec-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        padding: 24px 32px;
        border-radius: 16px;
        border-bottom: 3px solid #C5A059;
        color: #FFFFFF;
        margin-bottom: 22px;
        box-shadow: 0 12px 24px -6px rgba(15, 23, 42, 0.14);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .exec-header h1 {
        font-size: 22px !important;
        font-weight: 700 !important;
        color: #FFFFFF !important;
        margin: 0 !important;
        letter-spacing: -0.02em;
    }
    .exec-header p {
        font-size: 13px;
        color: #CBD5E1;
        margin: 5px 0 0 0;
    }

    .metric-container {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 14px;
        margin-bottom: 22px;
    }
    .metric-card {
        background: #FFFFFF;
        padding: 18px 20px;
        border-radius: 14px;
        border: 1px solid #E2E8F0;
        border-top: 3px solid #0F172A;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.03);
        display: flex;
        flex-direction: column;
        justify-content: center;
        min-height: 102px;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 16px -4px rgba(15, 23, 42, 0.08);
    }
    .metric-title {
        font-size: 11px;
        text-transform: uppercase;
        font-weight: 700;
        letter-spacing: 0.07em;
        color: #64748B;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 25px;
        font-weight: 800;
        color: #0F172A;
        letter-spacing: -0.03em;
        line-height: 1.2;
    }
    .metric-badge-live {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        background: rgba(226, 199, 146, 0.14);
        color: #E2C792;
        border: 1px solid rgba(226, 199, 146, 0.35);
        font-weight: 600;
        font-size: 12px;
        padding: 6px 13px;
        border-radius: 20px;
    }
    .dot-live {
        width: 8px;
        height: 8px;
        background: #10B981;
        border-radius: 50%;
        box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.25);
    }

    /* Carduri dosare pentru mobil */
    .mobile-dosar-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #0F172A;
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 10px;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.03);
    }
    .mobile-dosar-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
        margin-bottom: 6px;
    }
    .mobile-dosar-nr {
        font-family: monospace;
        font-weight: 700;
        font-size: 13px;
        background: #0F172A;
        color: #E2C792;
        padding: 3px 9px;
        border-radius: 6px;
    }
    .mobile-dosar-inst {
        font-size: 12px;
        font-weight: 600;
        color: #475569;
        text-align: right;
    }
    .mobile-dosar-meta {
        font-size: 13px;
        color: #1E293B;
        line-height: 1.45;
    }
    .mobile-dosar-minuta {
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid #F1F5F9;
        font-size: 12px;
        color: #64748B;
        line-height: 1.4;
    }

    .mobile-only-cards { display: none; }

    .ai-card {
        background: #FFFFFF;
        border-radius: 14px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 10px -2px rgba(15, 23, 42, 0.04);
        padding: 22px;
        margin-bottom: 16px;
    }
    .ai-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 10px;
        border-bottom: 1px solid #F1F5F9;
        padding-bottom: 14px;
        margin-bottom: 16px;
    }
    .dosar-tag {
        font-family: monospace;
        background: #0F172A;
        color: #E2C792;
        font-weight: 700;
        font-size: 14px;
        padding: 5px 11px;
        border-radius: 7px;
    }
    .prio-urgent {
        font-size: 11px;
        font-weight: 700;
        padding: 4px 11px;
        border-radius: 20px;
        background: #FEF2F2;
        color: #DC2626;
        border: 1px solid #FCA5A5;
    }
    .prio-important {
        font-size: 11px;
        font-weight: 700;
        padding: 4px 11px;
        border-radius: 20px;
        background: #FFFBEB;
        color: #B45309;
        border: 1px solid #FCD34D;
    }
    .prio-istoric {
        font-size: 11px;
        font-weight: 700;
        padding: 4px 11px;
        border-radius: 20px;
        background: #F1F5F9;
        color: #475569;
        border: 1px solid #CBD5E1;
    }

    .client-box {
        background: #F8FAFC;
        border-left: 4px solid #0F172A;
        padding: 15px 18px;
        border-radius: 0 10px 10px 0;
        font-size: 14px;
        line-height: 1.6;
        color: #1E293B;
        margin: 12px 0 4px 0;
        white-space: pre-line;
    }
    .sarcini-box {
        background: #FAF8F5;
        border-left: 4px solid #C5A059;
        padding: 14px 18px;
        border-radius: 0 10px 10px 0;
        font-size: 13.5px;
        color: #1E293B;
        margin-bottom: 14px;
        line-height: 1.6;
        white-space: pre-line;
    }

    div.stButton > button:first-child {
        background: #0F172A;
        color: #E2C792;
        border-radius: 10px;
        padding: 10px 18px;
        font-weight: 600;
        border: 1px solid #1E293B;
        transition: all 0.2s ease;
    }
    div.stButton > button:first-child:hover {
        background: #1E293B;
        color: #FFFFFF;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.18);
    }

    a[kind="secondary"] {
        background: #0F172A !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }
    a[kind="secondary"]:hover {
        background: #1E293B !important;
        color: #E2C792 !important;
    }

    /* Sidebar stilizat ca meniu modern */
    [data-testid="stSidebar"] {
        background-color: #0F172A !important;
        border-right: 1px solid #1E293B;
    }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] div {
        color: #F1F5F9 !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: #1E293B !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] {
        width: 100% !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label > div:not([data-testid="stMarkdownContainer"]):not(:has(p)) {
        display: none !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label [data-testid="stMarkdownContainer"] {
        display: block !important;
        width: 100% !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label {
        background: rgba(30, 41, 59, 0.65) !important;
        border: 1px solid rgba(148, 163, 184, 0.15) !important;
        padding: 11px 14px !important;
        border-radius: 10px !important;
        margin-bottom: 6px !important;
        width: 100% !important;
        font-weight: 600 !important;
        transition: all 0.15s ease !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
        background: #1E293B !important;
        border-left: 3px solid #C5A059 !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {
        color: #E2C792 !important;
    }

    @media (max-width: 768px) {
        .block-container {
            padding-top: 2.8rem !important;
            padding-bottom: 90px !important;
            padding-left: 0.85rem !important;
            padding-right: 0.85rem !important;
        }
        .metric-container {
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }
        .metric-card {
            padding: 14px 14px;
            min-height: 94px;
        }
        .metric-value {
            font-size: 21px;
        }
        .metric-channel-text {
            font-size: 13px !important;
        }
        .exec-header {
            padding: 18px 20px;
            flex-direction: column;
            align-items: flex-start;
            gap: 10px;
        }
        .exec-header h1 {
            font-size: 19px !important;
        }
        .ai-card {
            padding: 16px;
        }
        [data-testid="stDataFrame"] {
            display: none !important;
        }
        .mobile-only-cards {
            display: block !important;
        }
    }
</style>
""", unsafe_allow_html=True)

if st.session_state.pop("force_logout_msg", False):
    components.html("<script>if(window.top){window.top.postMessage({type:'errata_logout'}, '*');}</script>", height=0, width=0)

# ----------------- ECRAN AUTENTIFICARE / ÎNREGISTRARE -----------------
if not st.session_state.utilizator:
    st.markdown(f"""
        <div style='text-align: center; margin-top: 28px; margin-bottom: 22px;'>
            <img src="{ERRATA_ICON_DATA_URI}" width="64" height="64" style="border-radius: 16px; box-shadow: 0 8px 20px rgba(15,23,42,0.18); margin-bottom: 10px;" />
            <h1 style='font-family: "Playfair Display", Georgia, serif; color: #0F172A; font-weight: 700; font-size: 34px; margin: 0; letter-spacing: -0.02em;'>Errata</h1>
            <p style='color: #C5A059; font-size: 11px; font-weight: 700; letter-spacing: 0.22em; text-transform: uppercase; margin: 4px 0 8px 0;'>ASISTENT JURIDIC</p>
            <p style='color: #64748B; font-size: 13.5px;'>Securitate. Integritate. Rapiditate. — Monitorizare inteligentă Portal Just</p>
        </div>
    """, unsafe_allow_html=True)

    _, col_centru, _ = st.columns([1, 1.35, 1])
    with col_centru:
        tab_login, tab_inregistrare = st.tabs(["🔐 Conectare Cabinet", "📝 Deschide Cont Nou"])

        with tab_login:
            with st.form("form_login"):
                email_login = st.text_input("Email profesional", placeholder="avocat@societate.ro")
                parola_login = st.text_input("Parolă securizată", type="password")
                remember_me = st.checkbox("Ține-mă minte (30 zile)", value=True, key="chk_remember_me")
                btn_login = st.form_submit_button("Autentificare în Errata", use_container_width=True)

                if btn_login:
                    user = baza_date.autentifica_utilizator(email_login, parola_login)
                    if user:
                        st.session_state.utilizator = user
                        st.session_state.keep_logged_in = bool(remember_me)
                        if remember_me:
                            st.query_params["session"] = _gen_session_token(user)
                        st.success("Autentificare reușită!")
                        st.rerun()
                    else:
                        st.error("Credențiale invalide.")

        with tab_inregistrare:
            with st.form("form_register"):
                firma_noua = st.text_input("Denumire Societate / Cabinet Avocat", placeholder="ex: Popovici & Asociații SCA")
                email_nou = st.text_input("Email administrator", placeholder="contact@societate.ro")
                parola_noua = st.text_input("Parolă cont (minim 8 caractere)", type="password")
                acord_gdpr = st.checkbox("Accept Termenii de Utilizare și Politica de Confidențialitate (GDPR)")
                btn_reg = st.form_submit_button("Creează Cont Cabinet (Trial Gratuit)", use_container_width=True)

                if btn_reg:
                    if not (firma_noua and email_nou and parola_noua):
                        st.error("Toate câmpurile sunt obligatorii.")
                    elif len(parola_noua) < 8:
                        st.error("Parola trebuie să conțină minim 8 caractere.")
                    elif not acord_gdpr:
                        st.error("Trebuie să accepți Termenii și Politica GDPR pentru a crea contul.")
                    else:
                        succes, msg = baza_date.inregistreaza_companie(firma_noua, email_nou, parola_noua)
                        if succes:
                            st.success(msg + " Te poți autentifica acum.")
                        else:
                            st.error(msg)
    st.stop()

# ----------------- ECRAN PRINCIPAL DUPĂ LOGIN -----------------
user = st.session_state.utilizator
companie_id = user["id"]
APP_PUBLIC_URL = "https://app.errata.ro"

if st.session_state.get("keep_logged_in", True):
    tok_curent = _gen_session_token(user)
    if "session" not in st.query_params:
        st.query_params["session"] = tok_curent
    components.html(
        f"<script>if(window.top){{window.top.postMessage({{type:'errata_session', token:{json.dumps(tok_curent)}}}, '*');}}</script>",
        height=0,
        width=0
    )

st.sidebar.markdown(f"""
    <div style='padding: 6px 0 14px 0; display: flex; align-items: center; gap: 12px;'>
        <img src="{ERRATA_ICON_DATA_URI}" width="42" height="42" style="border-radius: 10px; border: 1px solid #C5A05955;" />
        <div>
            <div style='font-family: "Playfair Display", Georgia, serif; font-size: 20px; font-weight: 700; color: #E2C792 !important; line-height: 1.1;'>Errata</div>
            <div style='font-size: 10px; letter-spacing: 0.14em; color: #94A3B8 !important; text-transform: uppercase;'>ASISTENT JURIDIC</div>
        </div>
    </div>
    <div style='background: #1E293B; padding: 10px 12px; border-radius: 10px; margin-bottom: 12px;'>
        <div style='font-size: 10px; text-transform: uppercase; color: #94A3B8 !important; font-weight: 700;'>CABINET ACTIV</div>
        <div style='font-size: 15px; font-weight: 700; color: #FFFFFF !important;'>{user['nume_firma']}</div>
        <div style='font-size: 11px; color: #CBD5E1 !important;'>{user['email']}</div>
    </div>
""", unsafe_allow_html=True)

if st.sidebar.button("Deconectare Securizată 🚪", use_container_width=True):
    deconectare()

st.sidebar.write("---")
detalii_comp = baza_date.obtine_detalii_companie(companie_id) or {
    "plan": "trial", "limita_dosare": 2, "telegram_chat_id": "", "status_abonament": "active", "data_expirare": ""
}

stripe_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
if stripe_key:
    stripe.api_key = stripe_key
    q_params = st.query_params
    if "stripe_session" in q_params:
        sess_id = q_params["stripe_session"]
        try:
            sess_obj = stripe.checkout.Session.retrieve(sess_id)
            sess_dict = sess_obj.to_dict() if hasattr(sess_obj, "to_dict") else dict(sess_obj)
            if sess_dict.get("payment_status") == "paid":
                meta = dict(sess_dict.get("metadata") or {})
                plan_ales = meta.get("plan", "starter")
                limita_noua = int(meta.get("limita", 30))
                exp_str = (datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y")
                baza_date.activeaza_plan_companie(
                    companie_id, plan_ales, limita_noua,
                    stripe_customer_id=str(sess_dict.get("customer") or ""),
                    data_expirare=exp_str,
                    stripe_subscription_id=str(sess_dict.get("subscription") or "")
                )
                st.query_params.pop("stripe_session", None)
                st.success(f"Plata a fost confirmată! Planul {plan_ales.upper()} este activ până la {exp_str}.")
                detalii_comp = baza_date.obtine_detalii_companie(companie_id)
            else:
                st.query_params.pop("stripe_session", None)
        except Exception as se:
            st.query_params.pop("stripe_session", None)
            st.warning(f"Verificare plată în curs: {se}")

if stripe_key and detalii_comp.get("plan") not in ("trial", "enterprise", "expirat"):
    sub_id = baza_date.obtine_subscription_id_companie(companie_id)
    if sub_id:
        try:
            sub_obj = stripe.Subscription.retrieve(sub_id)
            sub_dict = sub_obj.to_dict() if hasattr(sub_obj, "to_dict") else dict(sub_obj)
            if sub_dict.get("status") not in ("active", "trialing"):
                baza_date.dezactiveaza_abonament_expirat(companie_id)
                detalii_comp = baza_date.obtine_detalii_companie(companie_id)
        except Exception:
            pass

st.sidebar.markdown(
    f"<div style='background:#1E293B;padding:10px 12px;border-radius:10px;margin-bottom:12px;font-size:12px;border-left:3px solid #C5A059;color:#F1F5F9 !important;'>"
    f"Plan activ: <strong style='color:#E2C792 !important;'>{detalii_comp['plan'].upper()}</strong><br/>"
    f"Capacitate: <strong>{detalii_comp['limita_dosare']} dosare</strong>"
    f"</div>",
    unsafe_allow_html=True
)

if detalii_comp.get("plan") == "expirat":
    st.error("⚠️ Abonamentul acestui cabinet a expirat sau a fost anulat. Activează un plan **Starter** sau **Pro** din **💳 Setări & Abonament** pentru a relua monitorizarea.")

meniu = st.sidebar.radio(
    "Navigare",
    ["📊 Panou Monitorizare", "📥 Import & Căutare Portal", "⚖️ Triaj & Analiză AI", "💳 Setări & Abonament"],
    label_visibility="collapsed"
)


def _query_df(sql, params=()):
    conn = baza_date.conectare()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cols = [desc[0] for desc in cur.description] if cur.description else []
    conn.close()
    return pd.DataFrame(rows, columns=cols)


def incarca_dosare_firma():
    df_res = _query_df(
        "SELECT * FROM dosare WHERE activ = 1 AND companie_id = ? ORDER BY id DESC",
        (companie_id,)
    )
    if not df_res.empty and "institutie" in df_res.columns:
        df_res["institutie"] = df_res["institutie"].apply(lambda x: app.formateaza_nume_institutie(str(x or "")))
    return df_res


def incarca_alerte_firma():
    query = """
    SELECT a.*, d.nume_client, d.contact_client, d.institutie, d.stadiu, d.ultima_minuta 
    FROM alerte a
    LEFT JOIN dosare d ON a.numar_dosar = d.numar_dosar AND a.companie_id = d.companie_id
    WHERE a.companie_id = ? 
    ORDER BY a.id DESC
    """
    df_a = _query_df(query, (companie_id,))
    if not df_a.empty and "numar_dosar" in df_a.columns:
        df_a = df_a.drop_duplicates(subset=["numar_dosar"], keep="first")
    return df_a


def _afiseaza_paywall_upgrade(companie_id: int, user_email: str, stripe_key: str):
    st.markdown("""
        <div style="background:#FAF8F5;border:1px solid #C5A059;border-radius:12px;padding:16px 20px;margin:14px 0;">
            <strong style="color:#0F172A;font-size:15px;">🚀 Extinde capacitatea portofoliului în Errata</strong><br/>
            <span style="color:#475569;font-size:13px;">Alege unul dintre planurile dedicate cabinetelor de avocatură pentru a adăuga dosare nelimitat în limita planului:</span>
        </div>
    """, unsafe_allow_html=True)
    cp1, cp2 = st.columns(2, gap="large")
    with cp1:
        st.markdown("""
            <div class="metric-card" style="min-height: 165px;">
                <div class="metric-title">CABINET STARTER</div>
                <div class="metric-value">149 RON<span style="font-size:13px;color:#64748B;">/lună</span></div>
                <p style="font-size:13px;color:#475569;margin-top:8px;line-height:1.55;">
- Până la <strong>30 dosare</strong> active<br/>
- Triaj AI (Urgent / Important / Istoric)<br/>
- Alerte pe <code>alerte@errata.ro</code>, Telegram & Calendar
                </p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Activează Starter (149 RON)", key="pw_btn_starter", use_container_width=True):
            if not stripe_key:
                st.warning("Configurează STRIPE_SECRET_KEY în Secrets.")
            else:
                try:
                    sess = stripe.checkout.Session.create(
                        line_items=[{
                            "price_data": {
                                "currency": "ron",
                                "product_data": {"name": "Errata — Plan Cabinet Starter (30 dosare)"},
                                "unit_amount": 14900,
                                "recurring": {"interval": "month"},
                            },
                            "quantity": 1,
                        }],
                        mode="subscription",
                        customer_email=user_email,
                        metadata={"companie_id": str(companie_id), "plan": "starter", "limita": "30"},
                        success_url=f"{APP_PUBLIC_URL}?stripe_session={{CHECKOUT_SESSION_ID}}",
                        cancel_url=APP_PUBLIC_URL,
                    )
                    st.link_button("💳 Mergi la Plata Securizată Stripe", sess.url, use_container_width=True)
                except Exception as e:
                    st.error(f"Eroare Stripe: {e}")

    with cp2:
        st.markdown("""
            <div class="metric-card" style="min-height: 165px;">
                <div class="metric-title">SOCIETATE PRO</div>
                <div class="metric-value">349 RON<span style="font-size:13px;color:#64748B;">/lună</span></div>
                <p style="font-size:13px;color:#475569;margin-top:8px;line-height:1.55;">
- Până la <strong>150 dosare</strong> active<br/>
- Căutare masivă după nume parte + Import lot<br/>
- Rapoarte PDF executive + Export registru
                </p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Activează Pro (349 RON)", key="pw_btn_pro", use_container_width=True):
            if not stripe_key:
                st.warning("Configurează STRIPE_SECRET_KEY în Secrets.")
            else:
                try:
                    sess = stripe.checkout.Session.create(
                        line_items=[{
                            "price_data": {
                                "currency": "ron",
                                "product_data": {"name": "Errata — Plan Societate Pro (150 dosare)"},
                                "unit_amount": 34900,
                                "recurring": {"interval": "month"},
                            },
                            "quantity": 1,
                        }],
                        mode="subscription",
                        customer_email=user_email,
                        metadata={"companie_id": str(companie_id), "plan": "pro", "limita": "150"},
                        success_url=f"{APP_PUBLIC_URL}?stripe_session={{CHECKOUT_SESSION_ID}}",
                        cancel_url=APP_PUBLIC_URL,
                    )
                    st.link_button("💳 Mergi la Plata Securizată Stripe", sess.url, use_container_width=True)
                except Exception as e:
                    st.error(f"Eroare Stripe: {e}")


# VEDERE 1: Panou Monitorizare
if meniu == "📊 Panou Monitorizare":
    st.markdown(f"""
        <div class="exec-header">
            <div>
                <h1>Panou Executiv — {user['nume_firma']}</h1>
                <p>Supraveghere automată Portal Just, triaj procedural și generare termene</p>
            </div>
            <div>
                <span class="metric-badge-live"><span class="dot-live"></span> Portal Just Conectat</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    df = incarca_dosare_firma()
    df_alerte = incarca_alerte_firma()

    nr_dosare = len(df)
    nr_urgente = sum(1 for _, r in df_alerte.iterrows() if extrage_prioritate_alerta(r)[0] == "URGENT") if not df_alerte.empty else 0
    nr_instante = df["institutie"].nunique() if not df.empty and "institutie" in df else 0

    st.markdown(f"""
        <div class="metric-container">
            <div class="metric-card">
                <div class="metric-title">Dosare Monitorizate</div>
                <div class="metric-value">{nr_dosare} <span style="font-size:13px;color:#64748B;font-weight:500;">/ {detalii_comp['limita_dosare']}</span></div>
            </div>
            <div class="metric-card" style="border-top-color: #DC2626;">
                <div class="metric-title">Alerte Urgente</div>
                <div class="metric-value" style="color: {'#DC2626' if nr_urgente > 0 else '#0F172A'};">{nr_urgente}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Instanțe Active</div>
                <div class="metric-value">{nr_instante}</div>
            </div>
            <div class="metric-card" style="border-top-color: #C5A059;">
                <div class="metric-title">Canale Alertare</div>
                <div class="metric-value metric-channel-text" style="font-size: 16px; color: #0F172A; padding-top: 4px;">Email • Telegram • ICS</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    col_btn, col_exp, _ = st.columns([1.8, 1.5, 2.5])
    with col_btn:
        if st.button("🚀 Sincronizează Acum", use_container_width=True):
            with st.spinner("Se interoghează Portal Just și se analizează minutele..."):
                nr_gasite = app.sincronizeaza_toate_dosarele(companie_id)
            if getattr(app, "ULTIMELE_ERORI", None):
                for er in app.ULTIMELE_ERORI:
                    st.error(er)
            else:
                st.success(f"Sincronizare finalizată! ({nr_gasite} actualizări noi detectate)")
                st.rerun()

    if not df.empty:
        with col_exp:
            csv_data = df[["numar_dosar", "nume_client", "institutie", "obiect", "stadiu", "ultima_minuta"]].to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 Export Registru CSV",
                data=csv_data,
                file_name=f"Registru_Errata_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )

        c1_f, c2_f = st.columns([2.5, 1.5])
        with c1_f:
            cautare = st.text_input("🔍 Căutare rapidă după număr dosar, client sau obiect", "")
        with c2_f:
            instante_list = ["Toate instanțele"] + sorted([i for i in df["institutie"].dropna().unique() if str(i).strip()])
            filtru_inst = st.selectbox("🏛️ Filtrează după instanță", instante_list)

        df_filtrat = df.copy()
        if cautare:
            df_filtrat = df_filtrat[
                df_filtrat["numar_dosar"].str.contains(cautare, case=False, na=False) |
                df_filtrat["nume_client"].str.contains(cautare, case=False, na=False) |
                df_filtrat["obiect"].str.contains(cautare, case=False, na=False)
            ]
        if filtru_inst != "Toate instanțele":
            df_filtrat = df_filtrat[df_filtrat["institutie"] == filtru_inst]

        # Tabel complet pe Desktop (ascuns automat pe mobil via CSS)
        afisaj = df_filtrat[[
            "numar_dosar", "nume_client", "institutie", "obiect", "stadiu", "ultima_minuta"
        ]].rename(columns={
            "numar_dosar": "Număr Dosar",
            "nume_client": "Client",
            "institutie": "Instanță",
            "obiect": "Obiect",
            "stadiu": "Stadiu",
            "ultima_minuta": "Ultima Minută / Stadiu"
        })
        st.dataframe(afisaj, use_container_width=True, hide_index=True)

        # Carduri compacte pe Telefon
        cards_html = ['<div class="mobile-only-cards">']
        for _, r_d in df_filtrat.iterrows():
            cl_txt = str(r_d.get("nume_client") or "Nespecificat")
            ob_txt = str(r_d.get("obiect") or "-")
            st_txt = str(r_d.get("stadiu") or "-")
            min_txt = str(r_d.get("ultima_minuta") or "În așteptare sincronizare")
            if len(min_txt) > 190:
                min_txt = min_txt[:187] + "..."
            cards_html.append(
                f'<div class="mobile-dosar-card">'
                f'<div class="mobile-dosar-top">'
                f'<span class="mobile-dosar-nr">{r_d["numar_dosar"]}</span>'
                f'<span class="mobile-dosar-inst">{r_d.get("institutie", "")}</span>'
                f'</div>'
                f'<div class="mobile-dosar-meta">'
                f'<strong>Client:</strong> {cl_txt} &bull; <strong>Stadiu:</strong> {st_txt}<br/>'
                f'<strong>Obiect:</strong> {ob_txt}'
                f'</div>'
                f'<div class="mobile-dosar-minuta">{min_txt}</div>'
                f'</div>'
            )
        cards_html.append("</div>")
        st.markdown("".join(cards_html), unsafe_allow_html=True)

        st.write("")
        c_del1, c_del2 = st.columns([3, 1])
        with c_del1:
            lista_stergere = df["numar_dosar"].tolist() if "numar_dosar" in df.columns else []
            dosar_ales_del = st.selectbox("🗑️ Elimină un dosar din monitorizare:", lista_stergere if lista_stergere else ["Niciun dosar"])
        with c_del2:
            st.write("")
            st.write("")
            if st.button("Șterge Dosar", use_container_width=True):
                if dosar_ales_del and dosar_ales_del != "Niciun dosar":
                    baza_date.sterge_dosar(companie_id, dosar_ales_del)
                    st.success(f"Dosarul {dosar_ales_del} a fost eliminat!")
                    st.rerun()
    else:
        st.info("Portofoliul este gol. Folosește **📥 Import & Căutare Portal** pentru a adăuga dosare individual, prin listă sau după numele clientului.")

# VEDERE 2: Import & Căutare Portal
elif meniu == "📥 Import & Căutare Portal":
    st.markdown("""
        <div class="exec-header">
            <div>
                <h1>Import Dosare & Căutare Portal Just</h1>
                <p>Adăugare individuală, import în lot (Copy-Paste / Excel) sau căutare automată după numele clientului</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    tab1, tab_parte, tab_paste, tab2 = st.tabs([
        "➕ Dosar Individual",
        "🔎 Căutare după Nume Parte",
        "📋 Import Rapid (Copy-Paste)",
        "📂 Import Registru (Excel / CSV)"
    ])

    with tab1:
        with st.form("form_add"):
            c_nr, c_cl = st.columns(2)
            with c_nr:
                nr = st.text_input("Număr dosar oficial *", placeholder="ex: 3654/2/2024")
            with c_cl:
                cl = st.text_input("Client reprezentat", placeholder="ex: SC Apex Logistics SRL")
            ct = st.text_input("Număr contact client (WhatsApp)", placeholder="ex: 0722123456")

            salveaza = st.form_submit_button("Înregistrează Dosarul în Errata")
            if salveaza:
                permis, nr_crt, lim_max = baza_date.verifica_limita_dosare(companie_id)
                if not nr.strip():
                    st.error("Introduceți numărul dosarului!")
                elif not permis:
                    st.session_state["arata_paywall_import"] = True
                    st.error(f"Ai atins limita planului curent ({nr_crt}/{lim_max} dosare).")
                else:
                    rez_add = baza_date.adauga_dosar(companie_id, nr, cl, ct)
                    ok_add, msg_add = rez_add if isinstance(rez_add, tuple) else (rez_add, "Dosar adăugat.")
                    if ok_add:
                        st.success(msg_add)
                    else:
                        st.warning(msg_add)

    with tab_parte:
        st.caption("Caută direct în baza Portal Just toate dosarele în care apare numele unui client sau al unei societăți.")
        with st.form("form_cauta_parte"):
            nume_cautat = st.text_input("Nume parte / Societate *", placeholder="ex: SC Apex Logistics SRL sau Popescu Ion")
            btn_cauta_p = st.form_submit_button("Caută în Portal Just")
            if btn_cauta_p:
                if len(nume_cautat.strip()) < 3:
                    st.error("Introdu cel puțin 3 caractere pentru căutare.")
                else:
                    with st.spinner("Se interoghează Portal Just..."):
                        st.session_state["rezultate_parte"] = app.cauta_dosare_dupa_parte(nume_cautat)
                        st.session_state["client_parte_cautat"] = nume_cautat.strip()

        rez_p = st.session_state.get("rezultate_parte")
        if rez_p is not None:
            if not rez_p:
                st.warning("Nu au fost găsite dosare pentru acest nume pe Portal Just.")
            else:
                st.success(f"Au fost găsite {len(rez_p)} dosare:")
                optiuni_p = {f"{r['numar_dosar']} — {r['institutie']} ({r['obiect']})": r for r in rez_p}
                selectate = st.multiselect("Selectează dosarele pe care dorești să le importezi în Errata:", list(optiuni_p.keys()))
                if st.button("Importă Dosarele Selectate", key="btn_imp_parte"):
                    imp_ok = 0
                    for key_sel in selectate:
                        permis, _, _ = baza_date.verifica_limita_dosare(companie_id)
                        if not permis:
                            st.warning("Import oprit la atingerea limitei de dosare a planului.")
                            break
                        item_p = optiuni_p[key_sel]
                        rez_a = baza_date.adauga_dosar(
                            companie_id,
                            item_p["numar_dosar"],
                            st.session_state.get("client_parte_cautat", ""),
                            ""
                        )
                        if (rez_a[0] if isinstance(rez_a, tuple) else rez_a):
                            imp_ok += 1
                    st.success(f"Au fost importate {imp_ok} dosare în portofoliu!")

    with tab_paste:
        st.caption("Lipește o listă de numere de dosar (câte unul pe linie sau separate prin virgulă) pentru import instant.")
        lista_bruta = st.text_area("Listă numere de dosar", height=160, placeholder="1234/2/2025\n5678/3/2025\n9101/300/2026")
        client_lot = st.text_input("Etichetă Client comună (opțional)", placeholder="ex: Portofoliu Banca X")
        if st.button("Importă Lista de Dosare"):
            linii = [x.strip() for x in lista_bruta.replace(",", "\n").replace(";", "\n").splitlines() if x.strip()]
            if not linii:
                st.error("Introdu cel puțin un număr de dosar.")
            else:
                count_p = 0
                for nr_item in linii:
                    permis, _, _ = baza_date.verifica_limita_dosare(companie_id)
                    if not permis:
                        st.warning("Import oprit la atingerea limitei de dosare a planului.")
                        break
                    rez_l = baza_date.adauga_dosar(companie_id, nr_item, client_lot.strip(), "")
                    if (rez_l[0] if isinstance(rez_l, tuple) else rez_l):
                        count_p += 1
                st.success(f"Au fost importate cu succes {count_p} dosare!")

    with tab2:
        st.write("Încarcă un registru electronic existent (`.xlsx` sau `.csv`):")
        fisier = st.file_uploader("Selectează fișierul", type=["xlsx", "csv"])
        if fisier is not None:
            try:
                df_up = pd.read_csv(fisier) if fisier.name.endswith(".csv") else pd.read_excel(fisier)
                st.dataframe(df_up.head(4), use_container_width=True)

                cols = df_up.columns.tolist()
                col_dos = st.selectbox("Coloană Număr Dosar:", cols)
                col_nume = st.selectbox("Coloană Nume Client (opțional):", ["-- Fără --"] + cols)
                col_tel = st.selectbox("Coloană Telefon / WhatsApp (opțional):", ["-- Fără --"] + cols)

                if st.button("Inițiază Importul Masiv"):
                    count = 0
                    oprit_limita = False
                    for _, row in df_up.iterrows():
                        permis, _, _ = baza_date.verifica_limita_dosare(companie_id)
                        if not permis:
                            oprit_limita = True
                            break
                        numar_val = str(row[col_dos]).strip()
                        nume_val = str(row[col_nume]).strip() if col_nume != "-- Fără --" else ""
                        tel_val = str(row[col_tel]).strip() if col_tel != "-- Fără --" else ""
                        if numar_val and numar_val.lower() != "nan":
                            rez_imp = baza_date.adauga_dosar(companie_id, numar_val, nume_val, tel_val)
                            ok_imp = rez_imp[0] if isinstance(rez_imp, tuple) else rez_imp
                            if ok_imp:
                                count += 1
                    st.success(f"Au fost importate cu succes {count} dosare!")
                    if oprit_limita:
                        st.warning("Import oprit la atingerea limitei de dosare a planului.")
                        _afiseaza_paywall_upgrade(companie_id, user["email"], stripe_key)
            except Exception as ex:
                st.error(f"Eroare procesare fișier: {ex}")

    permis_acum, _, _ = baza_date.verifica_limita_dosare(companie_id)
    if st.session_state.get("arata_paywall_import") or not permis_acum:
        _afiseaza_paywall_upgrade(companie_id, user["email"], stripe_key)

# VEDERE 3: Triaj & Analiză AI
elif meniu == "⚖️ Triaj & Analiză AI":
    st.markdown("""
        <div class="exec-header">
            <div>
                <h1>Triaj Procedural & Inteligență Juridică</h1>
                <p>Clasificare automată Urgent / Important / Istoric, fișe PDF și sincronizare calendar</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    df_alerte = incarca_alerte_firma()

    if not df_alerte.empty:
        c_filt1, c_filt2 = st.columns([2, 1.5])
        with c_filt1:
            conn_sel = baza_date.conectare()
            c_sel = conn_sel.cursor()
            c_sel.execute("SELECT numar_dosar, nume_client FROM dosare WHERE companie_id = ?", (companie_id,))
            dosare_disponibile = c_sel.fetchall()
            conn_sel.close()
            map_nume = {"Toate dosarele din portofoliu": None}
            for nr, cl in dosare_disponibile:
                map_nume[f"{nr} — {cl or 'Fără client'}"] = nr
            ales_key = st.selectbox("📌 Filtrează după dosar:", list(map_nume.keys()))
            nr_ales = map_nume[ales_key]

        with c_filt2:
            filtru_prio = st.selectbox("🚦 Nivel urgență procedurală:", ["Toate nivelurile", "🔴 URGENT", "🟡 IMPORTANT", "⚪ ISTORIC"])

        df_alerte_lucru = df_alerte.copy()
        if nr_ales:
            df_alerte_lucru = df_alerte_lucru[df_alerte_lucru["numar_dosar"] == nr_ales]

        afisate = 0
        for idx, row in df_alerte_lucru.iterrows():
            prio_code, sarcini_curate = extrage_prioritate_alerta(row)
            if filtru_prio == "🔴 URGENT" and prio_code != "URGENT":
                continue
            if filtru_prio == "🟡 IMPORTANT" and prio_code != "IMPORTANT":
                continue
            if filtru_prio == "⚪ ISTORIC" and prio_code != "ISTORIC":
                continue

            afisate += 1
            prio_cls = "prio-urgent" if prio_code == "URGENT" else ("prio-important" if prio_code == "IMPORTANT" else "prio-istoric")
            prio_lbl = "🔴 URGENT" if prio_code == "URGENT" else ("🟡 IMPORTANT" if prio_code == "IMPORTANT" else "⚪ ISTORIC")
            noul_t = row["noul_termen"] if row["noul_termen"] and str(row["noul_termen"]).lower() != "null" else "Fără termen stabilit"
            inst_frumos = app.formateaza_nume_institutie(row.get("institutie", "Instanță"))
            mesaj_client_afis = app._aplica_semnatura_cabinet(str(row.get("mesaj_client") or ""), user["nume_firma"])

            st.markdown(f"""
                <div class="ai-card">
                    <div class="ai-card-header">
                        <div>
                            <span class="dosar-tag">{row['numar_dosar']}</span>
                            <span style="margin-left: 10px; font-weight: 600; font-size: 14px; color: #0F172A;">
                                {inst_frumos}
                            </span>
                            <span style="margin-left: 8px; font-size: 13px; color: #64748B;">
                                {('• ' + row['nume_client']) if row.get('nume_client') else ''}
                            </span>
                        </div>
                        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                            <span class="{prio_cls}">{prio_lbl}</span>
                            <span class="prio-istoric" style="background:#0F172A;color:#E2C792;border:none;">{row['tip_solutie']}</span>
                        </div>
                    </div>
                    <div style="font-size: 13px; color: #475569; margin-bottom: 12px;">
                        <strong>Următorul Eveniment Procedural:</strong> <span style="color: #0F172A; font-weight: 700;">{noul_t}</span>
                    </div>
                    <div class="sarcini-box"><strong>📌 Evaluare Procedurală & Sarcini Cabinet:</strong>
{sarcini_curate}</div>
                    <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: #64748B; margin-top: 12px;">
                        Notificare Client Pre-Generată:
                    </div>
                    <div class="client-box">{mesaj_client_afis}</div>
                </div>
            """, unsafe_allow_html=True)

            tel_formatat = formateaza_telefon_whatsapp(row.get("contact_client"))
            mesaj_codificat = urllib.parse.quote(mesaj_client_afis)

            if tel_formatat:
                link_wa = f"https://wa.me/{tel_formatat}?text={mesaj_codificat}"
                label_btn = f"📲 WhatsApp ({row.get('nume_client', 'Client')})"
            else:
                link_wa = f"https://wa.me/?text={mesaj_codificat}"
                label_btn = "📲 WhatsApp Client"

            link_gcal = calendar_sync.genereaza_link_google_calendar(
                row["numar_dosar"], inst_frumos, noul_t, sarcini_curate
            )
            ics_bytes = calendar_sync.genereaza_fisier_ics(
                row["numar_dosar"], inst_frumos, noul_t, sarcini_curate
            )

            c_wa, c_pdf, c_gcal, c_ical, c_reai = st.columns([1.3, 1.2, 1.2, 1.2, 1.1])

            with c_wa:
                st.link_button(label_btn, link_wa, use_container_width=True)

            with c_pdf:
                analiza_dict = {
                    "tip_solutie": row["tip_solutie"],
                    "noul_termen": row["noul_termen"],
                    "sarcini_avocat": sarcini_curate,
                    "mesaj_client": mesaj_client_afis
                }
                pdf_bytes = export_pdf.genereaza_raport_dosar_pdf(
                    firma_nume=user["nume_firma"],
                    numar_dosar=row["numar_dosar"],
                    client_nume=row.get("nume_client", ""),
                    institutie=inst_frumos,
                    stadiu=row.get("stadiu", "Fond"),
                    solutie_sumar=row.get("ultima_minuta", mesaj_client_afis),
                    analiza=analiza_dict
                )
                st.download_button(
                    label="📄 Fișă PDF",
                    data=pdf_bytes,
                    file_name=f"Errata_Fisa_{row['numar_dosar'].replace('/', '_')}.pdf",
                    key=f"btn_pdf_{idx}_{row.get('id', idx)}",
                    mime="application/pdf",
                    use_container_width=True
                )

            with c_gcal:
                if link_gcal:
                    st.link_button("🌐 Google Cal", link_gcal, use_container_width=True)
                else:
                    st.button("🌐 Google Cal", disabled=True, use_container_width=True, help="Fără termen viitor consemnat", key=f"btn_gcal_dis_{idx}_{row.get('id', idx)}")

            with c_ical:
                st.download_button(
                    label="📅 Apple (.ics)",
                    data=ics_bytes,
                    file_name=f"Termen_{row['numar_dosar'].replace('/', '_')}.ics",
                    key=f"btn_ics_{idx}_{row.get('id', idx)}",
                    mime="text/calendar",
                    use_container_width=True
                )

            with c_reai:
                if st.button("🔄 Re-analizează", key=f"btn_reai_{idx}_{row.get('id', idx)}", use_container_width=True, help="Regenerează analiza juridică cu noul motor AI"):
                    with st.spinner("Se reanalizează dosarul..."):
                        ok_r, err_r = app.reanalizeaza_dosar_individual(companie_id, row["numar_dosar"])
                    if ok_r:
                        st.rerun()
                    elif err_r:
                        st.error(err_r)
            st.write("")

        if afisate == 0:
            st.info("Nicio alertă nu corespunde filtrului selectat.")
    else:
        st.info("Nu există alerte generate încă. Apasă **Sincronizează Acum** din Panoul de Monitorizare.")

# VEDERE 4: Setări & Abonament
elif meniu == "💳 Setări & Abonament":
    st.markdown("""
        <div class="exec-header">
            <div>
                <h1>Configurare Alertare & Abonament Errata</h1>
                <p>Canale automate de notificare pentru cabinet și administrare plan</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.subheader("🔔 Canale de Alertare Automată")
    col_tg, col_em = st.columns(2, gap="large")

    with col_tg:
        with st.container(border=True):
            st.markdown("#### 📲 Alertare Instant Telegram")
            st.caption("Primește instant pronunțările și termenele noi pe Telegram.")
            with st.form("form_tg_settings", border=False):
                tg_val = st.text_input(
                    "Telegram Chat ID",
                    value=detalii_comp.get("telegram_chat_id", ""),
                    placeholder="ex: 8359525029",
                    help="Deschide @userinfobot pe Telegram și apasă Start pentru a afla Chat ID-ul tău."
                )
                c_save_tg, c_test_tg = st.columns(2)
                with c_save_tg:
                    save_tg = st.form_submit_button("Salvează ID", use_container_width=True)
                with c_test_tg:
                    test_tg = st.form_submit_button("Trimite Test", use_container_width=True)

                if save_tg or test_tg:
                    baza_date.actualizeaza_telegram_companie(companie_id, tg_val)
                    st.success("Telegram Chat ID salvat!")
                    if test_tg and tg_val.strip():
                        ok_t = notificari.trimite_notificare_telegram(
                            "TEST/2026", "Client Test", "Portal Errata",
                            {
                                "prioritate": "URGENT",
                                "tip_solutie": "Conexiune activă",
                                "noul_termen": "Configurat cu succes",
                                "cale_atac": "Nu este cazul la acest moment",
                                "sarcini_avocat": ["Vei primi aici toate minutele și termenele noi."],
                                "mesaj_client": f"Bună ziua,\n\nAlertarea pe Telegram este activată.\n\nCu respect,\n{user['nume_firma']}"
                            },
                            chat_id_destinatar=tg_val.strip()
                        )
                        if ok_t:
                            st.info("Mesaj Telegram trimis!")
                        else:
                            st.error("Pornește mai întâi o conversație (/start) cu botul pe Telegram.")

    with col_em:
        with st.container(border=True):
            st.markdown("#### 📧 Alertare Email Oficială (`alerte@errata.ro`)")
            st.caption("Primește rapoartele procedurale structurate direct pe emailul cabinetului.")
            raw_em = str(detalii_comp.get("email_notificari") or "")
            default_em = raw_em if "@" in raw_em else user["email"]
            with st.form("form_email_settings", border=False):
                em_val = st.text_input(
                    "Email notificări cabinet",
                    value=default_em,
                    placeholder="notificari@cabinet-avocat.ro"
                )
                c_save_em, c_test_em = st.columns(2)
                with c_save_em:
                    save_em = st.form_submit_button("Salvează Email", use_container_width=True)
                with c_test_em:
                    test_em = st.form_submit_button("Trimite Email Test", use_container_width=True)

                if save_em or test_em:
                    baza_date.actualizeaza_email_companie(companie_id, em_val)
                    st.success("Adresa de email salvată!")
                    if test_em and em_val.strip():
                        ok_e = notificari.trimite_notificare_email(
                            em_val.strip(), "TEST/2026", "Client Test", "Portal Errata",
                            {
                                "prioritate": "URGENT",
                                "tip_solutie": "Conexiune Email Errata Activă",
                                "noul_termen": "Configurat cu succes",
                                "cale_atac": "Nu este cazul la acest moment",
                                "sarcini_avocat": ["Vei primi aici toate minutele și termenele noi de pe alerte@errata.ro."],
                                "mesaj_client": f"Bună ziua,\n\nAlertarea pe email este activată.\n\nCu respect,\n{user['nume_firma']}"
                            }
                        )
                        if ok_e:
                            st.info("Email de test trimis de pe alerte@errata.ro! Verifică Inbox-ul.")
                        else:
                            st.error("Verifică dacă RESEND_API_KEY este salvat și domeniul errata.ro este Verified în Resend.")

    st.write("---")
    st.subheader("💎 Planuri & Facturare")
    exp_txt = f" | **Valabil până la:** `{detalii_comp['data_expirare']}`" if detalii_comp.get("data_expirare") else ""
    st.markdown(f"**Plan curent:** `{detalii_comp['plan'].upper()}` | **Limită activă:** `{detalii_comp['limita_dosare']} dosare`{exp_txt}")
    st.write("")

    c_p1, c_p2 = st.columns(2, gap="large")

    with c_p1:
        st.markdown("""
            <div class="metric-card" style="min-height: 175px;">
                <div class="metric-title">CABINET STARTER</div>
                <div class="metric-value">149 RON<span style="font-size:13px;color:#64748B;">/lună</span></div>
                <p style="font-size:13px;color:#475569;margin-top:10px;line-height:1.6;">
- Până la <strong>30 dosare</strong> active<br/>
- Verificare automată zilnică Portal Just<br/>
- Triaj AI + Alerte <code>alerte@errata.ro</code>, Telegram & Calendar
                </p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Activează Starter (149 RON)", use_container_width=True):
            if not stripe_key:
                st.warning("Configurează STRIPE_SECRET_KEY în Secrets pentru a activa plățile live.")
            else:
                try:
                    session = stripe.checkout.Session.create(
                        line_items=[{
                            "price_data": {
                                "currency": "ron",
                                "product_data": {"name": "Errata — Plan Cabinet Starter (30 dosare)"},
                                "unit_amount": 14900,
                                "recurring": {"interval": "month"},
                            },
                            "quantity": 1,
                        }],
                        mode="subscription",
                        customer_email=user["email"],
                        metadata={"companie_id": str(companie_id), "plan": "starter", "limita": "30"},
                        success_url=f"{APP_PUBLIC_URL}?stripe_session={{CHECKOUT_SESSION_ID}}",
                        cancel_url=APP_PUBLIC_URL,
                    )
                    st.link_button("💳 Mergi la Plata Securizată Stripe", session.url, use_container_width=True)
                except Exception as e:
                    st.error(f"Eroare Stripe: {e}")

    with c_p2:
        st.markdown("""
            <div class="metric-card" style="min-height: 175px;">
                <div class="metric-title">SOCIETATE PRO</div>
                <div class="metric-value">349 RON<span style="font-size:13px;color:#64748B;">/lună</span></div>
                <p style="font-size:13px;color:#475569;margin-top:10px;line-height:1.6;">
- Până la <strong>150 dosare</strong> active<br/>
- Căutare masivă după nume parte + Import lot<br/>
- Rapoarte PDF executive + Export registru
                </p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Activează Pro (349 RON)", use_container_width=True):
            if not stripe_key:
                st.warning("Configurează STRIPE_SECRET_KEY în Secrets pentru a activa plățile live.")
            else:
                try:
                    session = stripe.checkout.Session.create(
                        line_items=[{
                            "price_data": {
                                "currency": "ron",
                                "product_data": {"name": "Errata — Plan Societate Pro (150 dosare)"},
                                "unit_amount": 34900,
                                "recurring": {"interval": "month"},
                            },
                            "quantity": 1,
                        }],
                        mode="subscription",
                        customer_email=user["email"],
                        metadata={"companie_id": str(companie_id), "plan": "pro", "limita": "150"},
                        success_url=f"{APP_PUBLIC_URL}?stripe_session={{CHECKOUT_SESSION_ID}}",
                        cancel_url=APP_PUBLIC_URL,
                    )
                    st.link_button("💳 Mergi la Plata Securizată Stripe", session.url, use_container_width=True)
                except Exception as e:
                    st.error(f"Eroare Stripe: {e}")
