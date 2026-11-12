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

def _get_secret(key):
    val = os.getenv(key, "").strip()
    if not val:
        try:
            import streamlit as st
            val = str(st.secrets.get(key, "")).strip()
        except Exception:
            pass
    return val

def analizeaza_cu_claude(numar_dosar, institutie, obiect, stadiu, minuta):
    global client_ai
    cheie = _get_secret("ANTHROPIC_API_KEY")
    if cheie and (client_ai is None or getattr(client_ai, "api_key", "") != cheie):
        client_ai = Anthropic(api_key=cheie)
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
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}]
        )
        raw = next((b.text for b in raspuns.content if getattr(b, "type", None) == "text" and hasattr(b, "text")), "").strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        return json.loads(raw)
    except Exception as e:
        print(f"Eroare la procesarea AI: {e}")
        return {"_eroare": str(e)}

ULTIMELE_ERORI = []

def sincronizeaza_toate_dosarele(companie_id=None):
    global ULTIMELE_ERORI
    ULTIMELE_ERORI = []
    dosare = baza_date.obtine_dosare_active(companie_id)
    if not dosare:
        return 0

    actualizari = 0
    for item in dosare:
        id_db, numar, client, contact, ultima_minuta_db, comp_id = item
        info = obtine_date_portal(numar)
        if not info:
            ULTIMELE_ERORI.append(f"{numar}: Portal Just nu a returnat date (verifică formatul sau conexiunea WSDL).")
            continue

        inst_str = str(getattr(info, "institutie", "") or "")
        obiect_str = str(getattr(info, "obiect", "") or "")
        stadiu_str = str(getattr(info, "stadiuProcesualNume", "") or "")

        if not (getattr(info, "sedinte", None) and getattr(info.sedinte, "DosarSedinta", None)):
            baza_date.actualizeaza_dosar(numar, comp_id, inst_str, obiect_str, stadiu_str, "", ultima_minuta_db or "Fără ședințe publicate")
            continue
            
        sedinta = info.sedinte.DosarSedinta[-1]
        minuta_curenta = sedinta.solutieSumar or "Fără soluție publicată"
        data_sedinta = str(sedinta.data)

        # Salvam mereu metadatele din Portal Just (pastrand ultima_minuta_db pana reuseste AI-ul)
        baza_date.actualizeaza_dosar(numar, comp_id, inst_str, obiect_str, stadiu_str, data_sedinta, ultima_minuta_db)

        if minuta_curenta != ultima_minuta_db:
            analiza = analizeaza_cu_claude(numar, inst_str, obiect_str, stadiu_str, minuta_curenta)
            if analiza and "_eroare" not in analiza:
                baza_date.salveaza_alerta(
                    comp_id,
                    numar,
                    analiza.get("tip_solutie"),
                    analiza.get("noul_termen"),
                    analiza.get("sarcini_avocat"),
                    analiza.get("mesaj_client")
                )
                
                termen = analiza.get("noul_termen")
                if termen and str(termen).lower() != "null":
                    calendar_sync.creeaza_eveniment_ics(numar, inst_str, termen)

                try:
                    notificari.trimite_notificare_telegram(numar, client, inst_str, analiza)
                except Exception as te:
                    ULTIMELE_ERORI.append(f"{numar} (Telegram): {te}")

                baza_date.actualizeaza_dosar(numar, comp_id, inst_str, obiect_str, stadiu_str, data_sedinta, minuta_curenta)
                actualizari += 1
            else:
                err_msg = analiza.get("_eroare") if isinstance(analiza, dict) else "Răspuns gol de la Claude"
                ULTIMELE_ERORI.append(f"{numar} (Claude AI): {err_msg}")
    return actualizari