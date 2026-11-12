import os
try:
    import streamlit as st
    for k, v in st.secrets.items():
        if isinstance(v, str) and k not in os.environ:
            os.environ[k] = v
except Exception:
    pass

import os
import json
import zeep
from dotenv import load_dotenv
from anthropic import Anthropic
import baza_date
import calendar_sync
import notificari

load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")
client_ai = Anthropic(api_key=api_key) if api_key else None
URL_WSDL = "http://portalquery.just.ro/query.asmx?WSDL"

def obtine_date_portal(numar_dosar):
    try:
        client_soap = zeep.Client(wsdl=URL_WSDL)
        rez = client_soap.service.CautareDosare2(
            numarDosar=numar_dosar,
            obiectDosar=None,
            numeParte=None,
            institutie=None,
            dataStart=None,
            dataStop=None
        )
        return rez[0] if rez else None
    except Exception as e:
        print(f"Eroare conectare Portal Just: {e}")
        return None

def analizeaza_cu_claude(numar_dosar, institutie, obiect, stadiu, minuta):
    prompt = f"""
Ești un asistent juridic de elită pentru instanțele din România.
Analizează minuta:
Dosar: {numar_dosar} | Instanță: {institutie} | Obiect: {obiect} | Stadiu: {stadiu}
Minută: "{minuta}"

Răspunde STRICT cu un obiect JSON valid, fără introduceri sau explicații în afara acoladelor:
{{
  "tip_solutie": "tipul soluției (ex: Amânare pronunțare, Amânare judecată, Admitere acțiune)",
  "noul_termen": "data exactă a noului termen sau pronunțării (ex: 20.06.2024) sau Null dacă nu există",
  "cale_atac": "termenul și calea de atac incidentă dacă reiese din minută",
  "sarcini_avocat": "1-2 sarcini procedurale clare pentru avocat/echipă",
  "mesaj_client": "mesaj complet, clar și empatic gata de trimis pe WhatsApp clientului"
}}
"""
    try:
        raspuns = client_ai.messages.create(
            model="claude-haiku-5-5",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = raspuns.content[0].text.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        return json.loads(raw)
    except Exception as e:
        print(f"Eroare la procesarea AI: {e}")
        return None

def sincronizeaza_toate_dosarele(companie_id=None):
    dosare = baza_date.obtine_dosare_active(companie_id)
    if not dosare:
        return 0

    actualizari = 0
    for item in dosare:
        id_db, numar, client, contact, ultima_minuta_db, comp_id = item
        info = obtine_date_portal(numar)
        if not info or not (info.sedinte and info.sedinte.DosarSedinta):
            continue
            
        sedinta = info.sedinte.DosarSedinta[-1]
        minuta_curenta = sedinta.solutieSumar or "Fără soluție publicată"
        data_sedinta = str(sedinta.data)

        if minuta_curenta != ultima_minuta_db:
            analiza = analizeaza_cu_claude(numar, info.institutie, info.obiect, info.stadiuProcesualNume, minuta_curenta)
            if analiza:
                baza_date.salveaza_alerta(
                    comp_id,
                    numar,
                    analiza.get("tip_solutie"),
                    analiza.get("noul_termen"),
                    analiza.get("sarcini_avocat"),
                    analiza.get("mesaj_client")
                )
                
                termen = analiza.get("noul_termen")
                if termen and termen.lower() != "null":
                    calendar_sync.creeaza_eveniment_ics(numar, info.institutie, termen)

                notificari.trimite_notificare_telegram(numar, client, info.institutie, analiza)
                actualizari += 1
            
            baza_date.actualizeaza_dosar(numar, comp_id, info.institutie, info.obiect, info.stadiuProcesualNume, data_sedinta, minuta_curenta)
    return actualizari