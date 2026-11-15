import os
import re
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


def formateaza_nume_institutie(raw_inst: str) -> str:
    """Transformă 'JudecatoriaONESTI' sau 'TribunalulBUCURESTI' în 'Judecătoria Onești' / 'Tribunalul București'."""
    if not raw_inst:
        return ""
    txt = str(raw_inst).strip()
    inlocuiri_prefix = [
        ("CurteadeApel", "Curtea de Apel "),
        ("Judecatoria", "Judecătoria "),
        ("TribunalulSpecializat", "Tribunalul Specializat "),
        ("Tribunalul", "Tribunalul "),
        ("InaltaCurte", "Înalta Curte "),
    ]
    for pref, frumos in inlocuiri_prefix:
        if txt.startswith(pref):
            rest = txt[len(pref):].strip()
            rest = re.sub(r"([A-ZĂÂÎȘȚ])(\d+)", r"\1 \2", rest)
            rest_title = " ".join(w.capitalize() for w in rest.split())
            diacritice_orase = {
                "Bucuresti": "București", "Onesti": "Onești", "Iasi": "Iași",
                "Timisoara": "Timișoara", "Constanta": "Constanța", "Brasov": "Brașov",
                "Galati": "Galați", "Ploiesti": "Ploiești", "Pitesti": "Pitești",
                "Targoviste": "Târgoviște", "Targu": "Târgu", "Botosani": "Botoșani",
                "Focsani": "Focșani", "Calarasi": "Călărași", "Resita": "Reșița",
                "Ramnicu": "Râmnicu", "Valcea": "Vâlcea", "Maramures": "Maramureș",
                "Mehedinti": "Mehedinți", "Salaj": "Sălaj", "Dambovita": "Dâmbovița",
                "Arges": "Argeș", "Bacau": "Bacău", "Braila": "Brăila",
                "Buzau": "Buzău", "Caras": "Caraș", "Severin": "Severin",
                "Mures": "Mureș", "Neamt": "Neamț", "Olt": "Olt", "Teleorman": "Teleorman",
                "Tulcea": "Tulcea", "Vaslui": "Vaslui", "Vrancea": "Vrancea",
                "Clujnapoca": "Cluj-Napoca", "Drobetaturnuseverin": "Drobeta-Turnu Severin",
                "Targumures": "Târgu Mureș", "Targujiu": "Târgu Jiu",
                "Piatraneamt": "Piatra-Neamț", "Bistritanasaud": "Bistrița-Năsăud",
                "Satumare": "Satu Mare", "Baiamare": "Baia Mare", "Albaiulia": "Alba Iulia",
                "Miercureaciuc": "Miercurea Ciuc", "Sfantu": "Sfântu", "Gheorghe": "Gheorghe",
                "Campina": "Câmpina", "Campulung": "Câmpulung", "Barlad": "Bârlad",
                "Husi": "Huși", "Falticeni": "Fălticeni", "Radauti": "Rădăuți",
                "Sighetu": "Sighetu", "Marmatiei": "Marmației", "Turnu": "Turnu",
                "Magurele": "Măgurele", "Rosiori": "Roșiori", "Caracal": "Caracal",
                "Slatina": "Slatina", "Dragasani": "Drăgășani", "Medgidia": "Medgidia",
                "Mangalia": "Mangalia", "Navodari": "Năvodari", "Fetesti": "Fetești",
                "Urziceni": "Urziceni", "Slobozia": "Slobozia", "Giurgiu": "Giurgiu",
                "Bolintin": "Bolintin", "Buftea": "Buftea", "Cornetu": "Cornetu",
            }
            for k_o, v_o in diacritice_orase.items():
                rest_title = re.sub(rf"\b{k_o}\b", v_o, rest_title)
            return f"{frumos}{rest_title}".strip()
    return txt


def extrage_parti_text(info) -> str:
    if not (getattr(info, "parti", None) and getattr(info.parti, "DosarParte", None)):
        return "Nespecificate"
    linii = []
    for p in info.parti.DosarParte:
        nume_p = str(getattr(p, "nume", "") or "").strip()
        cal_p = str(getattr(p, "calitateParte", "") or "").strip()
        if nume_p:
            linii.append(f"{nume_p} — {cal_p}" if cal_p else nume_p)
    return "; ".join(linii) if linii else "Nespecificate"


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
            rezultate.append({
                "numar_dosar": str(getattr(d, "numar", "") or "").strip(),
                "institutie": formateaza_nume_institutie(str(getattr(d, "institutie", "") or "")),
                "obiect": str(getattr(d, "obiect", "") or "").strip(),
                "stadiu": str(getattr(d, "stadiuProcesualNume", "") or "").strip(),
                "parti": extrage_parti_text(d)
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


def clasifica_prioritate_fallback(tip_solutie: str, minuta: str, are_termen_viitor: bool = False) -> str:
    txt = f"{tip_solutie} {minuta}".lower()
    cuvinte_urgente = [
        "respinge", "admite", "apel", "recurs", "contestație", "contestatie",
        "suspendă", "suspenda", "perimare", "anulează", "anuleaza", "obligă", "obliga",
        "pronunțare", "pronuntare", "hotărâre", "hotarare", "decizie", "sentință", "sentinta",
        "lipsă procedură", "lipsa procedura", "decădere", "decadere", "amendă", "amenda"
    ]
    if any(c in txt for c in cuvinte_urgente):
        return "URGENT"
    if are_termen_viitor or "amân" in txt or "aman" in txt or "termen" in txt:
        return "IMPORTANT"
    return "ISTORIC"


def analizeaza_cu_claude(numar_dosar, institutie, obiect, stadiu, minuta, client_nume="", parti_dosar="", istoric_sedinte=""):
    global client_ai
    cheie = _get_secret("ANTHROPIC_API_KEY")
    if cheie and (client_ai is None or getattr(client_ai, "api_key", "") != cheie):
        client_ai = Anthropic(api_key=cheie)

    prompt = f"""
Ești un avocat partener senior din Baroul București, specializat în procedură civilă și penală română, care redactează analize procedurale interne pentru echipa de avocați și informări oficiale către clienți.

DATE DOSAR:
- Număr dosar: {numar_dosar}
- Instanță: {institutie}
- Obiect: {obiect or 'Nespecificat'}
- Stadiu procesual: {stadiu or 'Nespecificat'}
- Clientul reprezentat de cabinetul nostru: {client_nume or 'Nespecificat (identifică din părți dacă este posibil)'}
- Părțile din dosar (Portal Just): {parti_dosar or 'Nespecificate'}
- Context ședințe anterioare: {istoric_sedinte or 'Prima înregistrare monitorizată'}

MINUTA / DISPOZIȚIA CURENTĂ DIN PORTAL JUST:
"{minuta}"

REGULI OBLIGATORII DE ANALIZĂ:
1. DISTINCȚIE INSTANȚĂ VS. AVOCAT: Nu confunda măsurile dispuse de instanță din oficiu (ex. „comunică intimatului întâmpinarea...”) cu sarcinile avocatului. Tradu efectul procedural în acțiuni concrete pentru avocatul nostru în funcție de calitatea clientului (ex. dacă clientul este Petent/Reclamant și se comunică întâmpinarea către Intimat, sarcina avocatului este să urmărească dovada comunicării la dosar, să verifice dacă intimatul depune întâmpinare în termenul legal de 25 de zile / termenul fixat și să pregătească răspunsul la întâmpinare / notele scrise înainte de următorul termen).
2. CORECTARE ERORI GREFIER: Dacă minuta conține greșeli evidente de redactare ale grefierului (ex. „înregistrarea” în loc de „întâmpinarea” sau „înscrisurile”), interpretează sensul juridic corect fără a propaga eroarea în mesajul către client.
3. CLASIFICARE PRIORITATE:
   - "URGENT": pronunțare pe fond/excepții, admitere/respingere, suspendare, perimare, amânare de pronunțare, obligații sub sancțiunea decăderii/amenzii sau curgerea unui termen de cale de atac.
   - "IMPORTANT": acordare termen de judecată, comunicări de acte procedurale, încuviințare/administrare probe (înscrisuri, martori, expertiză).
   - "ISTORIC": exclusiv înregistrare inițială fără termen sau modificări pur administrative fără termen viitor.
4. TONUL MESAJULUI CĂTRE CLIENT: Registru profesionist, calm, clar și politicos de cabinet de avocatură (începe cu „Bună ziua,” sau „Stimate domnule / Stimată doamnă,”, folosește exclusiv persoana a II-a plural „dumneavoastră”, explică pe scurt ce s-a întâmplat la termen, care este următorul pas și data următoarei ședințe, fără formule abrupte de tipul „Bună!” sau „sunați-mă!”).

Răspunde STRICT cu un obiect JSON valid, fără text în afara acoladelor:
{{
  "prioritate": "URGENT | IMPORTANT | ISTORIC",
  "tip_solutie": "denumirea juridică precisă a măsurii (ex: Amânare judecată — comunicare acte, Amânare pronunțare, Admitere cerere)",
  "noul_termen": "data exactă a noului termen sau pronunțării (ex: 19.11.2026) sau Null dacă nu există",
  "cale_atac": "calea de atac și termenul legal dacă hotărârea este supusă atacului, altfel 'Nu este cazul la acest moment'",
  "sarcini_avocat": "2-3 pași procedurali concreți pentru avocat, cu referire la termenul următor și calitatea clientului",
  "mesaj_client": "informare completă, elegantă și clară către client, gata de trimis"
}}
"""
    try:
        raspuns = client_ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1600,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}]
        )
        raw = next((b.text for b in raspuns.content if getattr(b, "type", None) == "text" and hasattr(b, "text")), "").strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        rez = json.loads(raw)
        are_termen = bool(rez.get("noul_termen") and str(rez.get("noul_termen")).lower() != "null")
        if not rez.get("prioritate") or (are_termen and str(rez.get("prioritate")).upper() == "ISTORIC"):
            rez["prioritate"] = clasifica_prioritate_fallback(rez.get("tip_solutie", ""), minuta, are_termen_viitor=are_termen)
        return rez
    except Exception as e:
        print(f"Eroare la procesarea AI: {e}")
        return {"_eroare": str(e)}


def _sterge_alerte_vechi_dosar(companie_id: int, numar_dosar: str):
    """Elimină analizele anterioare ale aceluiași dosar pentru a păstra doar varianta finală."""
    try:
        conn = baza_date.conectare()
        cur = conn.cursor()
        cur.execute("DELETE FROM alerte WHERE companie_id = ? AND numar_dosar = ?", (companie_id, numar_dosar))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Avertisment ștergere alerte vechi: {e}")


ULTIMELE_ERORI = []


def _proceseaza_un_dosar(comp_id, numar, client, ultima_minuta_db, forteaza_reanaliza=False):
    """Interoghează Portal Just pentru un dosar, actualizează BD și rulează analiza AI dacă e nouă sau forțată."""
    info = obtine_date_portal(numar)
    if not info:
        return False, f"{numar}: Portal Just nu a returnat date (verifică formatul sau conexiunea WSDL)."

    inst_str = formateaza_nume_institutie(str(getattr(info, "institutie", "") or ""))
    obiect_str = str(getattr(info, "obiect", "") or "")
    stadiu_str = str(getattr(info, "stadiuProcesualNume", "") or "")
    parti_str = extrage_parti_text(info)

    if not (getattr(info, "sedinte", None) and getattr(info.sedinte, "DosarSedinta", None)):
        baza_date.actualizeaza_dosar(numar, comp_id, inst_str, obiect_str, stadiu_str, "", ultima_minuta_db or "Fără ședințe publicate")
        return False, None

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

    istoric_scurt = " | ".join(
        f"{d.strftime('%d.%m.%Y') if d else ''}: {t[:180]}"
        for d, t, _ in sedinte_cu_minuta[-3:-1]
    )

    text_pentru_ai = minuta_curenta
    if termen_portal:
        text_pentru_ai += f" | Noul termen de judecată stabilit pe Portal Just: {termen_portal}"

    baza_date.actualizeaza_dosar(numar, comp_id, inst_str, obiect_str, stadiu_str, data_sedinta, ultima_minuta_db)

    if minuta_curenta != ultima_minuta_db or forteaza_reanaliza:
        analiza = analizeaza_cu_claude(
            numar, inst_str, obiect_str, stadiu_str, text_pentru_ai,
            client_nume=client, parti_dosar=parti_str, istoric_sedinte=istoric_scurt
        )
        if isinstance(analiza, dict) and "_eroare" not in analiza:
            if termen_portal and (not analiza.get("noul_termen") or str(analiza.get("noul_termen")).lower() == "null"):
                analiza["noul_termen"] = termen_portal

        if analiza and "_eroare" not in analiza:
            prio_tag = str(analiza.get("prioritate", "IMPORTANT")).upper()
            sarcini_extinse = analiza.get("sarcini_avocat", "")
            cale_atac_txt = analiza.get("cale_atac", "")
            if cale_atac_txt and cale_atac_txt.lower() not in ("null", "none", "fără cale de atac", "nu este cazul la acest moment"):
                sarcini_extinse = f"[{prio_tag}] {sarcini_extinse} | Cale atac: {cale_atac_txt}"
            else:
                sarcini_extinse = f"[{prio_tag}] {sarcini_extinse}"

            if forteaza_reanaliza:
                _sterge_alerte_vechi_dosar(comp_id, numar)

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

            if not forteaza_reanaliza:
                try:
                    det_comp = baza_date.obtine_detalii_companie(comp_id) or {}
                    email_dest = str(det_comp.get("email_notificari") or "").strip()
                    chat_dest = str(det_comp.get("telegram_chat_id") or "").strip()

                    if email_dest and "@" in email_dest:
                        notificari.trimite_notificare_email(email_dest, numar, client, inst_str, analiza)

                    if chat_dest:
                        notificari.trimite_notificare_telegram(numar, client, inst_str, analiza, chat_id_destinatar=chat_dest)
                except Exception as te:
                    return True, f"{numar} (Notificări): {te}"

            baza_date.actualizeaza_dosar(numar, comp_id, inst_str, obiect_str, stadiu_str, data_sedinta, minuta_curenta)
            return True, None
        else:
            err_msg = analiza.get("_eroare") if isinstance(analiza, dict) else "Răspuns gol de la Claude"
            return False, f"{numar} (Claude AI): {err_msg}"
    return False, None


def reanalizeaza_dosar_individual(companie_id: int, numar_dosar: str):
    """Re-rulează interogarea Portal Just și analiza AI de nivel senior pentru un dosar existent."""
    dosare = baza_date.obtine_dosare_active(companie_id) or []
    for item in dosare:
        _, numar, client, _, ultima_minuta_db, comp_id = item
        if str(numar).strip() == str(numar_dosar).strip():
            return _proceseaza_un_dosar(comp_id, numar, client, ultima_minuta_db, forteaza_reanaliza=True)
    return False, "Dosarul nu a fost găsit în portofoliul activ."


def sincronizeaza_toate_dosarele(companie_id=None):
    global ULTIMELE_ERORI
    ULTIMELE_ERORI = []
    dosare = baza_date.obtine_dosare_active(companie_id)
    if not dosare:
        return 0

    actualizari = 0
    for item in dosare:
        _, numar, client, _, ultima_minuta_db, comp_id = item
        ok, err = _proceseaza_un_dosar(comp_id, numar, client, ultima_minuta_db, forteaza_reanaliza=False)
        if ok:
            actualizari += 1
        if err:
            ULTIMELE_ERORI.append(err)
    return actualizari
