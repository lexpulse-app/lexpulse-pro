import os
try:
    import streamlit as st
    for k, v in st.secrets.items():
        if isinstance(v, str) and k not in os.environ:
            os.environ[k] = v
except Exception:
    pass

import json
import zeep
from datetime import datetime, date
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


def cauta_dosare_dupa_parte(nume_parte: str, institutie: str = None):
    """Caută toate dosarele din Portal Just în care apare numele părții/clientului."""
    if not nume_parte or len(nume_parte.strip()) < 3:
        return []
    try:
        client_soap = zeep.Client(wsdl=URL_WSDL)
        rez = client_soap.service.CautareDosare2(
            numarDosar=None,
            obiectDosar=None,
            numeParte=nume_parte.strip(),
            institutie=institutie if institutie and institutie != "Toate instanțele" else None,
            dataStart=None,
            dataStop=None
        )
        if not rez:
            return []
        rezultate = []
        for d in rez[:40]:
            parti_list = []
            if getattr(d, "parti", None) and getattr(d.parti, "DosarParte", None):
                for p in d.parti.DosarParte:
                    nume_p = str(getattr(p, "nume", "") or "").strip()
                    cal_p = str(getattr(p, "calitateParte", "") or "").strip()
                    if nume_p:
                        parti_list.append(f"{nume_p} ({cal_p})" if cal_p else nume_p)
            rezultate.append({
                "numar_dosar": str(getattr(d, "numar", "") or "").strip(),
                "institutie": str(getattr(d, "institutie", "") or "").strip(),
                "obiect": str(getattr(d, "obiect", "") or "").strip(),
                "stadiu": str(getattr(d, "stadiuProcesualNume", "") or "").strip(),
                "parti": ", ".join(parti_list[:4])
            })
        return rezultate
    except Exception as e:
        print(f"Eroare căutare după parte Portal Just: {e}")
        return []


def _get_secret(key):
    val = os.getenv(key, "").strip()
    if not val:
        try:
            import streamlit as st
            val = str(st.secrets.get(key, "")).strip()
        except Exception:
            pass
    return val


def clasifica_prioritate_fallback(tip_solutie: str, minuta: str) -> str:
    txt = f"{tip_solutie} {minuta}".lower()
    cuvinte_urgente = [
        "respinge", "admite", "apel", "recurs", "contestație", "contestatie",
        "suspendă", "suspenda", "perimare", "anulează", "anuleaza", "obligă", "obliga",
        "pronunțare", "pronuntare", "hotărâre", "hotarare", "decizie", "sentință", "sentinta"
    ]
    cuvinte_istoric = ["înregistrare", "inregistrare", "repartizare", "fără ședințe", "fara sedinte"]
    if any(c in txt for c in cuvinte_urgente):
        return "URGENT"
    if any(c in txt for c in cuvinte_istoric):
        return "ISTORIC"
    return "IMPORTANT"


def analizeaza_cu_claude(numar_dosar, institutie, obiect, stadiu, minuta):
    global client_ai
    cheie = _get_secret("ANTHROPIC_API_KEY")
    if cheie and (client_ai is None or getattr(client_ai, "api_key", "") != cheie):
        client_ai = Anthropic(api_key=cheie)
    prompt = f"""
Ești Errata, un asistent juridic de elită pentru avocații din România.
Analizează minuta de mai jos și clasifică rigoarea procedurală:
Dosar: {numar_dosar} | Instanță: {institutie} | Obiect: {obiect} | Stadiu: {stadiu}
Minută: "{minuta}"

Răspunde STRICT cu un obiect JSON valid, fără introduceri sau explicații în afara acoladelor:
{{
  "prioritate": "URGENT (dacă este pronunțare pe fond/excepție, respingere, admitere, suspendare, perimare sau curge termen de atac/depunere acte), IMPORTANT (dacă este fixare termen, amânare judecată, administrare probe/expertiză) sau ISTORIC (modificare administrativă fără impact imediat)",
  "tip_solutie": "tipul soluției (ex: Admitere în parte, Respingere excepție, Amânare pronunțare, Amânare judecată)",
  "noul_termen": "data exactă a noului termen sau pronunțării (ex: 20.06.2026) sau Null dacă nu există",
  "cale_atac": "termenul legal și calea de atac incidentă (ex: Apel în 30 zile de la comunicare) sau Fără cale de atac",
  "sarcini_avocat": "1-2 sarcini procedurale concrete și termene limită pentru avocat",
  "mesaj_client": "mesaj profesionist, clar și empatic gata de trimis pe WhatsApp/Email clientului"
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
        rez = json.loads(raw)
        if not rez.get("prioritate"):
            rez["prioritate"] = clasifica_prioritate_fallback(rez.get("tip_solutie", ""), minuta)
        return rez
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

        sedinte = list(info.sedinte.DosarSedinta)
        sedinte.sort(key=lambda s: str(getattr(s, "data", "") or ""))

        azi = date.today()
        termen_portal = None
        sedinte_viitoare = []
        sedinte_cu_minuta = []

        for s in sedinte:
            d_raw = getattr(s, "data", None)
            sumar = (getattr(s, "solutieSumar", None) or "").strip()
            sol = (getattr(s, "solutie", None) or "").strip()
            text_s = sumar or sol

            d_obj = None
            if hasattr(d_raw, "date"):
                d_obj = d_raw.date()
            elif isinstance(d_raw, date):
                d_obj = d_raw
            elif d_raw:
                try:
                    d_obj = datetime.fromisoformat(str(d_raw)[:10]).date()
                except Exception:
                    pass

            if d_obj and d_obj > azi:
                sedinte_viitoare.append((d_obj, text_s))
            if text_s:
                sedinte_cu_minuta.append((d_obj, text_s, str(d_raw or "")))

        if sedinte_viitoare:
            sedinte_viitoare.sort(key=lambda x: x[0])
            termen_portal = sedinte_viitoare[0][0].strftime("%d.%m.%Y")

        if sedinte_cu_minuta:
            _, minuta_curenta, data_sedinta = sedinte_cu_minuta[-1]
        else:
            ultima_sed = sedinte[-1]
            minuta_curenta = "Termen stabilit pe portal (fără soluție pronunțată încă)"
            data_sedinta = str(getattr(ultima_sed, "data", "") or "")

        text_pentru_ai = minuta_curenta
        if termen_portal:
            text_pentru_ai += f" | Noul termen de judecată stabilit pe Portal Just: {termen_portal}"

        baza_date.actualizeaza_dosar(numar, comp_id, inst_str, obiect_str, stadiu_str, data_sedinta, ultima_minuta_db)

        if minuta_curenta != ultima_minuta_db:
            analiza = analizeaza_cu_claude(numar, inst_str, obiect_str, stadiu_str, text_pentru_ai)
            if isinstance(analiza, dict) and "_eroare" not in analiza:
                if termen_portal and (not analiza.get("noul_termen") or str(analiza.get("noul_termen")).lower() == "null"):
                    analiza["noul_termen"] = termen_portal

            if analiza and "_eroare" not in analiza:
                prio_tag = str(analiza.get("prioritate", "IMPORTANT")).upper()
                sarcini_extinse = analiza.get("sarcini_avocat", "")
                cale_atac_txt = analiza.get("cale_atac", "")
                if cale_atac_txt and cale_atac_txt.lower() not in ("null", "none", "fără cale de atac"):
                    sarcini_extinse = f"[{prio_tag}] {sarcini_extinse} | Cale atac: {cale_atac_txt}"
                else:
                    sarcini_extinse = f"[{prio_tag}] {sarcini_extinse}"

                baza_date.salveaza_alerta(
                    comp_id,
                    numar,
                    analiza.get("tip_solutie"),
                    analiza.get("noul_termen"),
                    sarcini_extinse,
                    analiza.get("mesaj_client")
                )

                termen = analiza.get("noul_termen")
                if termen and str(termen).lower() != "null":
                    try:
                        if hasattr(calendar_sync, "creeaza_eveniment_ics"):
                            calendar_sync.creeaza_eveniment_ics(numar, inst_str, termen)
                        elif hasattr(calendar_sync, "genereaza_fisier_ics"):
                            ics_data = calendar_sync.genereaza_fisier_ics(numar, inst_str, termen, sarcini_extinse)
                            if ics_data:
                                with open(f"Termen_{numar.replace('/', '_')}.ics", "wb") as f_ics:
                                    f_ics.write(ics_data)
                    except Exception as ce:
                        print(f"Avertisment calendar_sync: {ce}")

                try:
                    det_comp = baza_date.obtine_detalii_companie(comp_id) or {}
                    email_dest = str(det_comp.get("email_notificari") or "").strip()
                    chat_dest = str(det_comp.get("telegram_chat_id") or "").strip()

                    if email_dest and "@" in email_dest:
                        notificari.trimite_notificare_email(email_dest, numar, client, inst_str, analiza)

                    if chat_dest:
                        notificari.trimite_notificare_telegram(numar, client, inst_str, analiza, chat_id_destinatar=chat_dest)
                except Exception as te:
                    ULTIMELE_ERORI.append(f"{numar} (Notificări): {te}")

                baza_date.actualizeaza_dosar(numar, comp_id, inst_str, obiect_str, stadiu_str, data_sedinta, minuta_curenta)
                actualizari += 1
            else:
                err_msg = analiza.get("_eroare") if isinstance(analiza, dict) else "Răspuns gol de la Claude"
                ULTIMELE_ERORI.append(f"{numar} (Claude AI): {err_msg}")
    return actualizari
