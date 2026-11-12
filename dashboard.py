import os
import json
import hmac
import hashlib
import base64
import time as _time_mod
import urllib.parse
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import stripe

for k in ["ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "DATABASE_URL", "STRIPE_SECRET_KEY"]:
    if k in st.secrets and not os.environ.get(k):
        os.environ[k] = str(st.secrets[k])

import baza_date
import app
import export_pdf
import calendar_sync

st.set_page_config(
    page_title="LexPulse Pro | Enterprise Legal Intelligence",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_resource
def _init_db_once():
    baza_date.init_db()
    return True

_init_db_once()

# ----------------- PERSISTENȚĂ SESIUNE 30 ZILE (HMAC TOKEN ÎN URL) -----------------
def _gen_session_token(user_dict: dict) -> str:
    secret = (os.getenv("DATABASE_URL") or "lexpulse_secret_salt").encode()
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
        secret = (os.getenv("DATABASE_URL") or "lexpulse_secret_salt").encode()
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

# Restaurare automată la refresh dacă există ?session=... valid
if not st.session_state.utilizator and "session" in st.query_params:
    restored_user = _verify_session_token(st.query_params["session"])
    if restored_user:
        st.session_state.utilizator = restored_user
        st.session_state.keep_logged_in = True

def deconectare():
    st.session_state.utilizator = None
    st.session_state.keep_logged_in = False
    st.query_params.pop("session", None)
    st.rerun()

def formateaza_telefon_whatsapp(telefon_raw):
    if not telefon_raw:
        return ""
    curat = "".join(filter(str.isdigit, str(telefon_raw)))
    if curat.startswith("0") and len(curat) == 10:
        return "4" + curat
    return curat

# ----------------- DESIGN SYSTEM / CUSTOM CSS -----------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .stApp {
        background-color: #F8FAFC;
    }
    
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        max-width: 1250px !important;
    }

    .exec-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        padding: 24px 32px;
        border-radius: 14px;
        color: #FFFFFF;
        margin-bottom: 24px;
        box-shadow: 0 10px 15px -3px rgba(15, 23, 42, 0.08);
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
        color: #94A3B8;
        margin: 4px 0 0 0;
    }

    .metric-container {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-bottom: 24px;
    }
    .metric-card {
        background: #FFFFFF;
        padding: 18px 20px;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px -2px rgba(0, 0, 0, 0.06);
    }
    .metric-title {
        font-size: 11px;
        text-transform: uppercase;
        font-weight: 700;
        letter-spacing: 0.06em;
        color: #64748B;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 26px;
        font-weight: 700;
        color: #0F172A;
        letter-spacing: -0.03em;
    }
    .metric-badge-live {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #ECFDF5;
        color: #059669;
        font-weight: 600;
        font-size: 13px;
        padding: 4px 10px;
        border-radius: 20px;
    }
    .dot-live {
        width: 8px;
        height: 8px;
        background: #10B981;
        border-radius: 50%;
        box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
    }

    .ai-card {
        background: #FFFFFF;
        border-radius: 14px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.04);
        padding: 24px;
        margin-bottom: 24px;
    }
    .ai-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #F1F5F9;
        padding-bottom: 14px;
        margin-bottom: 16px;
    }
    .dosar-tag {
        font-family: monospace;
        background: #F1F5F9;
        color: #0F172A;
        font-weight: 700;
        font-size: 14px;
        padding: 5px 10px;
        border-radius: 6px;
        border: 1px solid #CBD5E1;
    }
    .solutie-tag {
        font-size: 12px;
        font-weight: 600;
        padding: 5px 12px;
        border-radius: 20px;
        background: #FEF2F2;
        color: #DC2626;
        border: 1px solid #FCA5A5;
    }

    .client-box {
        background: #F8FAFC;
        border-left: 4px solid #3B82F6;
        padding: 16px 20px;
        border-radius: 0 10px 10px 0;
        font-size: 14px;
        line-height: 1.6;
        color: #1E293B;
        margin: 16px 0;
    }
    .sarcini-box {
        background: #FFFBEB;
        border-left: 4px solid #F59E0B;
        padding: 14px 18px;
        border-radius: 0 8px 8px 0;
        font-size: 13px;
        color: #78350F;
        margin-bottom: 16px;
        line-height: 1.5;
    }

    div.stButton > button:first-child {
        background: #0F172A;
        color: #FFFFFF;
        border-radius: 8px;
        padding: 8px 18px;
        font-weight: 600;
        border: none;
        transition: all 0.2s ease;
    }
    div.stButton > button:first-child:hover {
        background: #1E293B;
        color: #FFFFFF;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.15);
    }

    a[kind="secondary"] {
        background: #10B981 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    a[kind="secondary"]:hover {
        background: #059669 !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 10px rgba(16, 185, 129, 0.25) !important;
    }

    [data-testid="stSidebar"] {
        background-color: #0F172A;
    }
    [data-testid="stSidebar"] * {
        color: #F1F5F9 !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: #334155 !important;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- ECRAN AUTENTIFICARE / ÎNREGISTRARE -----------------
if not st.session_state.utilizator:
    st.markdown("""
        <div style='text-align: center; margin-top: 50px; margin-bottom: 25px;'>
            <h1 style='color: #0F172A; font-weight: 800; font-size: 32px; letter-spacing: -0.03em;'>⚖️ LexPulse Pro</h1>
            <p style='color: #64748B; font-size: 15px;'>Enterprise Legal Operations & Case Intelligence Platform</p>
        </div>
    """, unsafe_allow_html=True)

    _, col_centru, _ = st.columns([1, 1.4, 1])
    with col_centru:
        tab_login, tab_inregistrare = st.tabs(["🔐 Conectare Cabinet", "📝 Deschide Cont Nou"])

        with tab_login:
            with st.form("form_login"):
                email_login = st.text_input("Email profesional", placeholder="avocat@societate.ro")
                parola_login = st.text_input("Parolă securizată", type="password")
                remember_me = st.checkbox("Ține-mă minte (30 zile)", value=True, key="chk_remember_me")
                btn_login = st.form_submit_button("Autentificare în Portal", use_container_width=True)

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
                btn_reg = st.form_submit_button("Creează Cont Societate (Trial Gratuit)", use_container_width=True)

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

# Menținem ?session=... sincronizat în URL pe durata navigării și la întoarcerea din Stripe
if st.session_state.get("keep_logged_in", True):
    tok_curent = _gen_session_token(user)
    if "session" not in st.query_params:
        st.query_params["session"] = tok_curent

st.sidebar.markdown(f"""
    <div style='padding: 8px 0 16px 0;'>
        <div style='font-size: 11px; text-transform: uppercase; color: #94A3B8; font-weight: 700; letter-spacing: 0.05em;'>PORTAL ACTIV</div>
        <div style='font-size: 18px; font-weight: 700; color: #FFFFFF;'>{user['nume_firma']}</div>
        <div style='font-size: 12px; color: #64748B;'>{user['email']}</div>
    </div>
""", unsafe_allow_html=True)

if st.sidebar.button("Deconectare Securizată 🚪", use_container_width=True):
    deconectare()

st.sidebar.write("---")
detalii_comp = baza_date.obtine_detalii_companie(companie_id) or {
    "plan": "trial", "limita_dosare": 2, "telegram_chat_id": "", "status_abonament": "active", "data_expirare": ""
}

# Procesare automată revenire din Stripe Checkout (?stripe_session=...)
stripe_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
if stripe_key:
    stripe.api_key = stripe_key
    q_params = st.query_params
    if "stripe_session" in q_params:
        sess_id = q_params["stripe_session"]
        try:
            sess_obj = stripe.checkout.Session.retrieve(sess_id)
            sess_dict = sess_obj.to_dict_recursive() if hasattr(sess_obj, "to_dict_recursive") else dict(sess_obj)
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

st.sidebar.markdown(
    f"<div style='background:#1E293B;padding:10px 12px;border-radius:8px;margin-bottom:12px;font-size:12px;'>"
    f"Plan activ: <strong style='color:#38BDF8;'>{detalii_comp['plan'].upper()}</strong><br/>"
    f"Limită portofoliu: <strong>{detalii_comp['limita_dosare']} dosare</strong>"
    f"</div>",
    unsafe_allow_html=True
)

meniu = st.sidebar.radio(
    "Navigare",
    ["📊 Panou Monitorizare", "📥 Import & Adăugare", "⚖️ Soluții & Analiză AI", "💳 Setări & Abonament"]
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
    return _query_df(
        "SELECT * FROM dosare WHERE activ = 1 AND companie_id = ? ORDER BY id DESC",
        (companie_id,)
    )

def incarca_alerte_firma():
    query = """
    SELECT a.*, d.nume_client, d.contact_client, d.institutie, d.stadiu, d.ultima_minuta 
    FROM alerte a
    LEFT JOIN dosare d ON a.numar_dosar = d.numar_dosar AND a.companie_id = d.companie_id
    WHERE a.companie_id = ? 
    ORDER BY a.id DESC
    """
    return _query_df(query, (companie_id,))

# VEDERE 1: Panou Monitorizare
if meniu == "📊 Panou Monitorizare":
    st.markdown(f"""
        <div class="exec-header">
            <div>
                <h1>Panou Executiv — {user['nume_firma']}</h1>
                <p>Sistem automat de supraveghere a instanțelor și sumarizare decizională</p>
            </div>
            <div>
                <span class="metric-badge-live"><span class="dot-live"></span> Portal Just Conectat</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    df = incarca_dosare_firma()
    df_alerte = incarca_alerte_firma()
    
    nr_dosare = len(df)
    nr_alerte = len(df_alerte)
    nr_instante = df["institutie"].nunique() if not df.empty and "institutie" in df else 0
    
    st.markdown(f"""
        <div class="metric-container">
            <div class="metric-card">
                <div class="metric-title">Portofoliu Activ</div>
                <div class="metric-value">{nr_dosare}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Minute Procesate</div>
                <div class="metric-value">{nr_alerte}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Instanțe Monitorizate</div>
                <div class="metric-value">{nr_instante}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Protocol Criptare</div>
                <div class="metric-value" style="font-size: 18px; color: #10B981; padding-top: 6px;">AES-256 / WSDL</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    col_btn, _ = st.columns([1.8, 3.5])
    with col_btn:
        if st.button("🚀 Declanșează Sincronizare Acum", use_container_width=True):
            with st.spinner("Se interoghează baza centralizată Portal Just..."):
                nr_gasite = app.sincronizeaza_toate_dosarele(companie_id)
            if getattr(app, "ULTIMELE_ERORI", None):
                for er in app.ULTIMELE_ERORI:
                    st.error(er)
            else:
                st.success(f"Sincronizare finalizată! ({nr_gasite} actualizări recepționate)")
                st.rerun()

    st.write("")
    if not df.empty:
        cautare = st.text_input("🔍 Căutare rapidă după număr dosar sau client", "")
        df_filtrat = df.copy()
        if cautare:
            df_filtrat = df_filtrat[
                df_filtrat["numar_dosar"].str.contains(cautare, case=False, na=False) |
                df_filtrat["nume_client"].str.contains(cautare, case=False, na=False)
            ]

        afisaj = df_filtrat[[
            "numar_dosar", "nume_client", "institutie", "obiect", "stadiu", "ultima_minuta"
        ]].rename(columns={
            "numar_dosar": "Număr Dosar",
            "nume_client": "Client",
            "institutie": "Instanță",
            "obiect": "Obiect",
            "stadiu": "Stadiu",
            "ultima_minuta": "Ultima Soluție Publicată"
        })
        st.dataframe(afisaj, use_container_width=True)

        # --- GESTIONARE SI ELIMINARE DOSAR ---
        st.write('')
        c_del1, c_del2 = st.columns([3, 1])
        with c_del1:
            lista_stergere = df['numar_dosar'].tolist() if 'numar_dosar' in df.columns else []
            dosar_ales_del = st.selectbox('🗑️ Elimină un dosar din monitorizare:', lista_stergere if lista_stergere else ['Niciun dosar'])
        with c_del2:
            st.write('')
            st.write('')
            if st.button('Șterge Dosar', type='primary'):
                if dosar_ales_del and dosar_ales_del != 'Niciun dosar':
                    baza_date.sterge_dosar(companie_id, dosar_ales_del)
                    st.success(f'Dosarul {dosar_ales_del} a fost eliminat!')
                    st.rerun()
        # -------------------------------------

    else:
        st.info("Portofoliul firmei este gol. Utilizați 'Import & Adăugare' pentru primele cauze.")

# VEDERE 2: Import & Adăugare
elif meniu == "📥 Import & Adăugare":
    st.markdown("""
        <div class="exec-header">
            <div>
                <h1>Înregistrare Dosare în Monitorizare</h1>
                <p>Adăugare individuală sau preluare masivă din registrul intern al cabinetului</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Adăugare Dosar Individual", "📂 Import Masiv Registru (Excel / CSV)"])
    
    with tab1:
        with st.form("form_add"):
            c_nr, c_cl = st.columns(2)
            with c_nr:
                nr = st.text_input("Număr dosar oficial *", placeholder="ex: 3654/2/2024")
            with c_cl:
                cl = st.text_input("Client reprezentat", placeholder="ex: SC Apex Logistics SRL")
            ct = st.text_input("Număr contact client (WhatsApp)", placeholder="ex: 0722123456")
            
            salveaza = st.form_submit_button("Înregistrează Cauza în Supraveghere")
            if salveaza:
                permis, nr_crt, lim_max = baza_date.verifica_limita_dosare(companie_id)
                if not nr.strip():
                    st.error("Introduceți numărul dosarului!")
                elif not permis:
                    st.error(f"Ai atins limita planului curent ({nr_crt}/{lim_max} dosare). Accesează '💳 Setări & Abonament' pentru upgrade.")
                else:
                    rez_add = baza_date.adauga_dosar(companie_id, nr, cl, ct)
                    ok_add, msg_add = rez_add if isinstance(rez_add, tuple) else (rez_add, "Operațiune finalizată.")
                    if ok_add:
                        st.success(msg_add)
                    else:
                        st.warning(msg_add)

    with tab2:
        st.write("Încărcați un registru electronic existent (`.xlsx` sau `.csv`):")
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
                        st.warning("Import oprit la atingerea limitei de dosare a planului. Fă upgrade din '💳 Setări & Abonament'.")
            except Exception as ex:
                st.error(f"Eroare procesare fișier: {ex}")

# VEDERE 3: Feed Alerte & AI
elif meniu == "⚖️ Soluții & Analiză AI":
    st.markdown("""
        <div class="exec-header">
            <div>
                <h1>Flux Decizional & Inteligență Juridică</h1>
                <p>Minute procesate automat, aprecieri procedurale, export fișă și sincronizare calendar</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    df_alerte = incarca_alerte_firma()
    
    if not df_alerte.empty:
        conn_sel = baza_date.conectare()
        c_sel = conn_sel.cursor()
        c_sel.execute('SELECT numar_dosar, nume_client FROM dosare WHERE companie_id = ?', (companie_id,))
        dosare_disponibile = c_sel.fetchall()
        conn_sel.close()
        if dosare_disponibile:
            map_nume = {f'{nr} - {cl}': nr for nr, cl in dosare_disponibile}
            ales_key = st.selectbox('📌 Selectează Dosarul pentru Analiză AI & Strategie:', list(map_nume.keys()))
            nr_ales = map_nume[ales_key]
            df_alerte_lucru = df_alerte[df_alerte['numar_dosar'] == nr_ales] if ('numar_dosar' in df_alerte.columns and not df_alerte[df_alerte['numar_dosar'] == nr_ales].empty) else df_alerte
        else:
            df_alerte_lucru = df_alerte
        for idx, row in df_alerte_lucru.iterrows():
            noul_t = row['noul_termen'] if row['noul_termen'] and str(row['noul_termen']).lower() != "null" else "Fără termen stabilit"
            
            st.markdown(f"""
                <div class="ai-card">
                    <div class="ai-card-header">
                        <div>
                            <span class="dosar-tag">{row['numar_dosar']}</span>
                            <span style="margin-left: 10px; font-weight: 600; font-size: 14px; color: #475569;">
                                {row.get('institutie', 'Curtea de Apel')}
                            </span>
                        </div>
                        <div>
                            <span class="solutie-tag">{row['tip_solutie']}</span>
                        </div>
                    </div>
                    <div style="font-size: 13px; color: #64748B; margin-bottom: 12px;">
                        <strong>Următorul Eveniment Procedural:</strong> <span style="color: #0F172A; font-weight: 600;">{noul_t}</span>
                    </div>
                    <div class="sarcini-box">
                        <strong>📌 Evaluare Procedurală & Termene:</strong><br/>
                        {row['sarcini_avocat']}
                    </div>
                    <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #475569; margin-top: 14px;">
                        Notificare Client Pre-Generată:
                    </div>
                    <div class="client-box">
                        {row['mesaj_client']}
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            tel_formatat = formateaza_telefon_whatsapp(row.get('contact_client'))
            mesaj_codificat = urllib.parse.quote(row['mesaj_client'])
            
            if tel_formatat:
                link_wa = f"https://wa.me/{tel_formatat}?text={mesaj_codificat}"
                label_btn = f"📲 WhatsApp ({row.get('nume_client', 'Client')})"
            else:
                link_wa = f"https://wa.me/?text={mesaj_codificat}"
                label_btn = "📲 WhatsApp (Alege destinatar)"
            
            link_gcal = calendar_sync.genereaza_link_google_calendar(
                row['numar_dosar'], row.get('institutie', 'Instanță'), noul_t, row['sarcini_avocat']
            )
            ics_bytes = calendar_sync.genereaza_fisier_ics(
                row['numar_dosar'], row.get('institutie', 'Instanță'), noul_t, row['sarcini_avocat']
            )

            c_wa, c_pdf, c_gcal, c_ical = st.columns([1.5, 1.4, 1.3, 1.3])
            
            with c_wa:
                st.link_button(label_btn, link_wa, use_container_width=True)
                
            with c_pdf:
                analiza_dict = {
                    "tip_solutie": row['tip_solutie'],
                    "noul_termen": row['noul_termen'],
                    "sarcini_avocat": row['sarcini_avocat'],
                    "mesaj_client": row['mesaj_client']
                }
                pdf_bytes = export_pdf.genereaza_raport_dosar_pdf(
                    firma_nume=user['nume_firma'],
                    numar_dosar=row['numar_dosar'],
                    client_nume=row.get('nume_client', ''),
                    institutie=row.get('institutie', 'Curtea de Apel'),
                    stadiu=row.get('stadiu', 'Fond'),
                    solutie_sumar=row.get('ultima_minuta', row.get('mesaj_client', '')),
                    analiza=analiza_dict
                )
                st.download_button(
                    label="📄 Fișă PDF",
                    data=pdf_bytes,
                    file_name=f"Fisa_{row['numar_dosar'].replace('/', '_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            with c_gcal:
                if link_gcal:
                    st.link_button("🌐 Google Calendar", link_gcal, use_container_width=True)
                else:
                    st.button("🌐 Google Calendar", disabled=True, use_container_width=True, help="Fără termen viitor consemnat")

            with c_ical:
                st.download_button(
                    label="📅 Apple Calendar",
                    data=ics_bytes,
                    file_name=f"Termen_{row['numar_dosar'].replace('/', '_')}.ics",
                    mime="text/calendar",
                    use_container_width=True
                )
            st.write("")
    else:
        st.info("Nu există alerte generate pentru această firmă până acum.")

# VEDERE 4: Setări & Abonament
elif meniu == "💳 Setări & Abonament":
    st.markdown("""
        <div class="exec-header">
            <div>
                <h1>Configurare Notificări & Abonament SaaS</h1>
                <p>Conectare alertare individuală Telegram și administrare plan comercial</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    col_tg, col_plan = st.columns([1, 1.3])

    with col_tg:
        st.subheader("📲 Alertare Telegram Cabinet")
        st.caption("Fiecare cabinet primește notificările exclusiv pe propriul cont Telegram.")
        with st.form("form_tg_settings"):
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
                st.success("Telegram Chat ID salvat pentru acest cabinet!")
                if test_tg and tg_val.strip():
                    import notificari
                    ok_t = notificari.trimite_notificare_telegram(
                        "TEST/2026", "Client Test", "Portal LexPulse Pro",
                        {
                            "tip_solutie": "Conexiune activă",
                            "noul_termen": "Configurat cu succes",
                            "cale_atac": "N/A",
                            "sarcini_avocat": "Vei primi aici toate minutele și termenele noi.",
                            "mesaj_client": "Alertare activată pentru cabinetul dumneavoastră."
                        },
                        chat_id_destinatar=tg_val.strip()
                    )
                    if ok_t:
                        st.info("Mesaj de test trimis! Verifică telefonul.")
                    else:
                        st.error("Nu s-a putut trimite. Pornește mai întâi o conversație (/start) cu botul LexPulse pe Telegram.")

    with col_plan:
        st.subheader("💎 Planuri & Facturare")
        st.write(f"**Plan curent:** `{detalii_comp['plan'].upper()}` | **Limită:** `{detalii_comp['limita_dosare']} dosare`")
        if detalii_comp.get("data_expirare"):
            st.write(f"**Valabil până la:** {detalii_comp['data_expirare']}")

        app_url = "https://lexpulse-pro.streamlit.app"

        c_p1, c_p2 = st.columns(2)
        with c_p1:
            st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">CABINET STARTER</div>
                    <div class="metric-value">149 RON<span style="font-size:13px;color:#64748B;">/lună</span></div>
                    <p style="font-size:13px;color:#475569;margin-top:8px;">
                        • Până la <strong>30 dosare</strong> active<br/>
                        • Verificare automată zilnică<br/>
                        • Analiză AI + Telegram + Calendar
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
                                    "product_data": {"name": "LexPulse Pro — Plan Cabinet Starter (30 dosare)"},
                                    "unit_amount": 14900,
                                    "recurring": {"interval": "month"},
                                },
                                "quantity": 1,
                            }],
                            mode="subscription",
                            customer_email=user["email"],
                            metadata={"companie_id": str(companie_id), "plan": "starter", "limita": "30"},
                            success_url=f"{app_url}?stripe_session={{CHECKOUT_SESSION_ID}}",
                            cancel_url=app_url,
                        )
                        st.link_button("💳 Mergi la Plata Securizată Stripe", session.url, use_container_width=True)
                    except Exception as e:
                        st.error(f"Eroare Stripe: {e}")

        with c_p2:
            st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">SOCIETATE PRO</div>
                    <div class="metric-value">349 RON<span style="font-size:13px;color:#64748B;">/lună</span></div>
                    <p style="font-size:13px;color:#475569;margin-top:8px;">
                        • Până la <strong>150 dosare</strong> active<br/>
                        • Verificare automată 3x/zi<br/>
                        • Rapoarte PDF + Export registru
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
                                    "product_data": {"name": "LexPulse Pro — Plan Societate Pro (150 dosare)"},
                                    "unit_amount": 34900,
                                    "recurring": {"interval": "month"},
                                },
                                "quantity": 1,
                            }],
                            mode="subscription",
                            customer_email=user["email"],
                            metadata={"companie_id": str(companie_id), "plan": "pro", "limita": "150"},
                            success_url=f"{app_url}?stripe_session={{CHECKOUT_SESSION_ID}}",
                            cancel_url=app_url,
                        )
                        st.link_button("💳 Mergi la Plata Securizată Stripe", session.url, use_container_width=True)
                    except Exception as e:
                        st.error(f"Eroare Stripe: {e}")
