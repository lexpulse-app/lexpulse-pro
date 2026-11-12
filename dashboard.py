
import os
import streamlit as st
for k in ["ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]:
    if k in st.secrets and not os.environ.get(k):
        os.environ[k] = str(st.secrets[k])

import os
import json
import streamlit as st
import pandas as pd
import urllib.parse
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

FISIER_SESIUNE = ".sesiune_activa.json"

def citeste_sesiune_locala():
    if os.path.exists(FISIER_SESIUNE):
        try:
            with open(FISIER_SESIUNE, "r") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def salveaza_sesiune_locala(user_dict):
    with open(FISIER_SESIUNE, "w") as f:
        json.dump(user_dict, f)

def sterge_sesiune_locala():
    if os.path.exists(FISIER_SESIUNE):
        os.remove(FISIER_SESIUNE)

if "utilizator" not in st.session_state or st.session_state.utilizator is None:
    sesiune_salvata = citeste_sesiune_locala()
    if sesiune_salvata:
        st.session_state.utilizator = sesiune_salvata
    else:
        st.session_state.utilizator = None

def deconectare():
    sterge_sesiune_locala()
    st.session_state.utilizator = None
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
                tine_minte = st.checkbox("Păstrează sesiunea activă pe acest terminal", value=True)
                btn_login = st.form_submit_button("Autentificare în Portal", use_container_width=True)

                if btn_login:
                    user = baza_date.autentifica_utilizator(email_login, parola_login)
                    if user:
                        st.session_state.utilizator = user
                        if tine_minte:
                            salveaza_sesiune_locala(user)
                        st.success("Autentificare reușită!")
                        st.rerun()
                    else:
                        st.error("Credențiale invalide.")

        with tab_inregistrare:
            with st.form("form_register"):
                firma_noua = st.text_input("Denumire Societate / Cabinet Avocat", placeholder="ex: Popovici & Asociații SCA")
                email_nou = st.text_input("Email administrator", placeholder="contact@societate.ro")
                parola_noua = st.text_input("Parolă cont", type="password")
                btn_reg = st.form_submit_button("Creează Cont Societate", use_container_width=True)

                if btn_reg:
                    if not (firma_noua and email_nou and parola_noua):
                        st.error("Toate câmpurile sunt obligatorii.")
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
meniu = st.sidebar.radio(
    "Navigare",
    ["📊 Panou Monitorizare", "📥 Import & Adăugare", "⚖️ Soluții & Analiză AI"]
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
                if not nr.strip():
                    st.error("Introduceți numărul dosarului!")
                else:
                    if baza_date.adauga_dosar(companie_id, nr, cl, ct):
                        st.success(f"Dosarul {nr} a fost introdus cu succes!")
                    else:
                        st.warning("Dosarul există deja în monitorizarea cabinetului.")

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
                    for _, row in df_up.iterrows():
                        numar_val = str(row[col_dos]).strip()
                        nume_val = str(row[col_nume]).strip() if col_nume != "-- Fără --" else ""
                        tel_val = str(row[col_tel]).strip() if col_tel != "-- Fără --" else ""
                        if numar_val and numar_val.lower() != "nan":
                            if baza_date.adauga_dosar(companie_id, numar_val, nume_val, tel_val):
                                count += 1
                    st.success(f"Au fost importate cu succes {count} dosare!")
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
        # --- SELECTOR DINAMIC DOSARE PENTRU AI ---
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
            
            # WhatsApp link
            tel_formatat = formateaza_telefon_whatsapp(row.get('contact_client'))
            mesaj_codificat = urllib.parse.quote(row['mesaj_client'])
            
            if tel_formatat:
                link_wa = f"https://wa.me/{tel_formatat}?text={mesaj_codificat}"
                label_btn = f"📲 WhatsApp ({row.get('nume_client', 'Client')})"
            else:
                link_wa = f"https://wa.me/?text={mesaj_codificat}"
                label_btn = "📲 WhatsApp (Alege destinatar)"
            
            # Calendare
            link_gcal = calendar_sync.genereaza_link_google_calendar(
                row['numar_dosar'], row.get('institutie', 'Instanță'), noul_t, row['sarcini_avocat']
            )
            ics_bytes = calendar_sync.genereaza_fisier_ics(
                row['numar_dosar'], row.get('institutie', 'Instanță'), noul_t, row['sarcini_avocat']
            )

            # Rând de acțiuni: WhatsApp, Fișă PDF, Google Calendar, Apple / iCal
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