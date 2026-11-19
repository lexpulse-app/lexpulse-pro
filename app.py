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


def _pastreaza_cazul(original: str, inlocuire: str) -> str:
    if original.isupper():
        return inlocuire.upper()
    if original and original[0].isupper():
        return inlocuire[0].upper() + inlocuire[1:]
    return inlocuire


def curata_diacritice_portal(text: str) -> str:
    """Repară diacriticele corupte ('ã', 'ş', 'ţ' și '?' în loc de 'ș'/'ț') din răspunsurile Portal Just."""
    if not text:
        return ""
    txt = str(text)

    inlocuiri_directe = {
        "ã": "ă", "Ã": "Ă",
        "ş": "ș", "Ş": "Ș",
        "ţ": "ț", "Ţ": "Ț",
    }
    for k_d, v_d in inlocuiri_directe.items():
        txt = txt.replace(k_d, v_d)

    reguli_regex = [
        (r"([eăâîiuoaEĂÂÎIUOA])\?te\b", r"\1ște"),
        (r"([eăâîiuoaEĂÂÎIUOA])\?ti\b", r"\1ști"),
        (r"\b(ata|afi|înfăți|infati|depă|depa|pă|gre|sfâr|sfar|săvâr|savar)\?([aăeiî])", r"\1ș\2"),
        (r"\b(înștiin|instiin)\?", r"\1ț"),
        (r"\b(Bucure|Ploie|Pite|Târgovi|Targovi|One|Boto|Foc|Călăra|Calara|Re|Hu|Făltice|Faltice|Rădău|Radau|Fete|Roșio|Rosio|Buhu|Moine|Comăne|Comane)\?ti\b", r"\1ști"),
        (r"\b(Timi|Bra|Ia|Bârlă|Barla|Olt|Arge|Mure|Cara)\?([a-zăâîșț]*)", r"\1ș\2"),
        (r"\b(ș|s)edin\?", r"ședinț"),
        (r"\b\?edinț", r"ședinț"),
        (r"\?eaz([ăa])\b", r"țeaz\1"),
        (r"\?iun(e|ea|i|ii|ilor)\b", r"țiun\1"),
        (r"\b(instan|sentin|ordonan|contesta|cita|execu|preten|solu|excep|obliga|licita|garan|penalit|renun|men|sus|ob|re|înfiin|infiin|desfiin|încuviin|incuviin|pronun|ac|sec|peti|soma|dispozi|func|no|op|cau|pozi|frac|repara|declara|constata|înregistra|inregistra|înainta|inainta|comunica|prezenta|depune|achita|înceta|inceta|judeca|audi|administr|efectua|restitui|trimite|emite|dispune|stabili|acorda|amâna|amana|suspenda|perima|declina|conexa|disjunge|rectifica|lămuri|lamuri|completa|investi|învesti|legaliza|certifica|expedia|formul|invoc|motiv|doved|prob|expertiz|evalu|lichid|partaj|evacu|rezili|rezolu|anul|constat|oblig|condamn|achit|încet|incet|clas|trimit)\?", r"\1ț"),
        (r"\b(fa|bra|pre|so|ter|mar|ian|feb|apr|iun|iul|aug|sep|oct|noi|dec|mul|pu|to|al|atâ|ata|câ|ca|în|in)\?([ăaieîuo])", r"\1ț\2"),
        (r"([a-zA-ZăâîșțĂÂÎȘȚ])\?(ă|ii|ilor|ile|uri|urile)\b", r"\1ț\2"),
        (r"([a-zA-ZăâîșțĂÂÎȘȚ])\?([a-zA-ZăâîșțĂÂÎȘȚ])", r"\1ț\2"),
    ]

    for pattern, repl in reguli_regex:
        txt = re.sub(
            pattern,
            lambda m, r=repl: _pastreaza_cazul(m.group(0), m.expand(r)),
            txt,
            flags=re.IGNORECASE
        )

    return txt


def _curata_sarcini_afisare(sarcini_raw) -> str:
    """Formatează sarcinile avocatului pe rânduri distincte, curate, fără numerotări lipite."""
    if isinstance(sarcini_raw, list):
        items = [curata_diacritice_portal(str(x)).strip() for x in sarcini_raw if str(x).strip()]
    else:
        txt = curata_diacritice_portal(str(sarcini_raw or "")).strip()
        # Sparge inclusiv cazurile de tip "1. ...; 2. ...; 3. ..." într-o listă curată
        txt = re.sub(r";\s*(?=\d+[\.\)]\s*)", "\n", txt)
        items = [line.strip() for line in txt.splitlines() if line.strip()]

    curate = []
    for it in items:
        it = re.sub(r"^[•\-\*]+\s*", "", it)
        it = re.sub(r"^\d+[\.\)]\s*", "", it).strip()
        if it:
            curate.append(f"• {it}")
    return "\n".join(curate)


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
    return curata_diacritice_portal(txt)


def extrage_parti_text(info) -> str:
    if not (getattr(info, "parti", None) and getattr(info.parti, "DosarParte", None)):
        return "Nespecificate"
    linii = []
    for p in info.parti.DosarParte:
        nume_p = curata_diacritice_portal(str(getattr(p, "nume", "") or "").strip())
        cal_p = curata_diacritice_portal(str(getattr(p, "calitateParte", "") or "").strip())
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
                "obiect": curata_diacritice_portal(str(getattr(d, "obiect", "") or "").strip()),
                "stadiu": curata_diacritice_portal(str(getattr(d, "stadiuProcesualNume", "") or "").strip()),
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


def _aplica_semnatura_cabinet(mesaj_client: str, nume_cabinet: str) -> str:
    """Normalizează spațierea și încheie mesajul cu denumirea exactă a cabinetului."""
    semnatura = (nume_cabinet or "").strip() or "Echipa dvs. juridică"
    txt = curata_diacritice_portal(mesaj_client or "").strip()
    if not txt:
        return f"Bună ziua,\nVă informăm că a fost înregistrată o actualizare în dosarul dumneavoastră.\nCu respect,\n{semnatura}"

    inlocuiri_generice = [
        "Cabinetul dvs. de avocatură",
        "Cabinetul dumneavoastră de avocatură",
        "Cabinetul de avocatură",
        "[Numele Cabinetului]",
        "[Nume Cabinet]"
    ]
    for gen in inlocuiri_generice:
        if gen in txt:
            txt = txt.replace(gen, semnatura)

    # Elimină rândurile goale duble ca să nu apară spații uriașe în cardurile cu pre-line
    linii_curate = [l.strip() for l in txt.splitlines() if l.strip()]
    txt = "\n".join(linii_curate)

    if semnatura not in txt:
        txt = f"{txt}\nCu respect,\n{semnatura}"
    return txt


def analizeaza_cu_claude(numar_dosar, institutie, obiect, stadiu, minuta, client_nume="", parti_dosar="", istoric_sedinte="", nume_cabinet=""):
    global client_ai
    cheie = _get_secret("ANTHROPIC_API_KEY")
    if cheie and (client_ai is None or getattr(client_ai, "api_key", "") != cheie):
        client_ai = Anthropic(api_key=cheie)

    semnatura_cabinet = (nume_cabinet or "").strip() or "Echipa dvs. juridică"
    minuta_curata = curata_diacritice_portal(minuta)
    obiect_curat = curata_diacritice_portal(obiect)
    stadiu_curat = curata_diacritice_portal(stadiu)

    prompt = f"""
Ești un avocat partener senior din Baroul București, specializat în procedură civilă și penală română, care redactează note interne concise pentru echipa de avocați și informări oficiale către clienți.

DATE DOSAR:
- Cabinet / Societate de avocatură utilizatoare: {semnatura_cabinet}
- Număr dosar: {numar_dosar}
- Instanță: {institutie}
- Obiect: {obiect_curat or 'Nespecificat'}
- Stadiu procesual: {stadiu_curat or 'Nespecificat'}
- Clientul reprezentat de cabinetul nostru: {client_nume or 'Nespecificat (identifică din părți dacă este posibil)'}
- Părțile din dosar (Portal Just): {parti_dosar or 'Nespecificate'}
- Context ședințe anterioare: {istoric_sedinte or 'Prima înregistrare monitorizată'}

MINUTA / DISPOZIȚIA CURENTĂ DIN PORTAL JUST:
"{minuta_curata}"

REGULI OBLIGATORII DE ANALIZĂ ȘI REDACTARE:
1. DISTINCȚIE INSTANȚĂ VS. AVOCAT: Nu confunda măsurile dispuse de instanță din oficiu (ex. „comunică intimatului întâmpinarea...”) cu sarcinile avocatului. Tradu efectul procedural în 2–3 acțiuni concrete, scurte și clare pentru avocatul nostru, fără numerotări în text.
2. CORECTARE ERORI GREFIER & LIMBAJ JURIDIC NATURAL:
   - Folosește exclusiv limba română literară cu diacritice corecte (ă, â, î, ș, ț).
   - Dacă minuta conține o eroare de redactare a grefierului (ex. „comunicarea înregistrării” în loc de „comunicarea înscrisurilor”), folosește direct termenul juridic corect („înscrisurilor”), fără paranteze explicative greoaie.
   - Evită calc-urile din limba engleză (nu scrie „Între această dată și termenul următor”, „la cea mai apropiată dată convenabilă”, „analiză finală”). Folosește formulări firești în română (ex. „Până la următorul termen”, „în cel mai scurt timp posibil”).
3. CLASIFICARE PRIORITATE:
   - "URGENT": pronunțare pe fond/excepții, admitere/respingere, suspendare, perimare, amânare de pronunțare, obligații sub sancțiunea decăderii/amenzii sau curgerea unui termen de cale de atac.
   - "IMPORTANT": acordare termen de judecată, comunicări de acte procedurale, încuviințare/administrare probe (înscrisuri, martori, expertiză).
   - "ISTORIC": exclusiv înregistrare inițială fără termen sau modificări pur administrative fără termen viitor.
4. STRUCTURA MESAJULUI CĂTRE CLIENT (4 PARAGRAFE SCURTE, FĂRĂ BULINE):
   - Folosește consecvent persoana I plural („Vă informăm...”, „cabinetul nostru...”) și persoana a II-a plural („dumneavoastră”).
   - Exprimă datele calendaristice consecvent în formatul ZZ.LL.AAAA (ex. 19.11.2026).
   - Paragraful 1: „Bună ziua,” + menționarea dosarului nr. {numar_dosar} aflat pe rolul {institutie}.
   - Paragraful 2: Ce s-a dispus concret la termenul anterior, explicat clar pe înțelesul clientului.
   - Paragraful 3: Data noului termen de judecată (dacă există) și pașii pe care îi va urma cabinetul până la acel termen (plus ce documente trebuie să ne transmită clientul, dacă este cazul).
   - Paragraful 4: Formula de încheiere:
     Rămânem la dispoziția dumneavoastră pentru orice lămuriri suplimentare.
     Cu respect,
     {semnatura_cabinet}

Răspunde STRICT cu un obiect JSON valid, fără text în afara acoladelor:
{{
  "prioritate": "URGENT | IMPORTANT | ISTORIC",
  "tip_solutie": "denumirea juridică precisă a măsurii (ex: Amânare judecată — comunicare înscrisuri, Amânare pronunțare, Admitere cerere)",
  "noul_termen": "data exactă a noului termen sau pronunțării (ex: 19.11.2026) sau Null dacă nu există",
  "cale_atac": "calea de atac și termenul legal dacă hotărârea este supusă atacului, altfel 'Nu este cazul la acest moment'",
  "sarcini_avocat": ["acțiune concretă 1", "acțiune concretă 2", "acțiune concretă 3"],
  "mesaj_client": "informare completă, naturală și elegantă către client, semnată exact cu {semnatura_cabinet}"
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

        rez["tip_solutie"] = curata_diacritice_portal(rez.get("tip_solutie", ""))
        rez["sarcini_avocat"] = _curata_sarcini_afisare(rez.get("sarcini_avocat"))
        rez["mesaj_client"] = _aplica_semnatura_cabinet(rez.get("mesaj_client", ""), semnatura_cabinet)

        are_termen = bool(rez.get("noul_termen") and str(rez.get("noul_termen")).lower() != "null")
        if not rez.get("prioritate") or (are_termen and str(rez.get("prioritate")).upper() == "ISTORIC"):
            rez["prioritate"] = clasifica_prioritate_fallback(rez.get("tip_solutie", ""), minuta_curata, are_termen_viitor=are_termen)
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

    det_comp = baza_date.obtine_detalii_companie(comp_id) or {}
    nume_cabinet = str(det_comp.get("nume_firma") or "").strip()

    inst_str = formateaza_nume_institutie(str(getattr(info, "institutie", "") or ""))
    obiect_str = curata_diacritice_portal(str(getattr(info, "obiect", "") or ""))
    stadiu_str = curata_diacritice_portal(str(getattr(info, "stadiuProcesualNume", "") or ""))
    parti_str = extrage_parti_text(info)
    ultima_minuta_db_curata = curata_diacritice_portal(ultima_minuta_db or "")

    if not (getattr(info, "sedinte", None) and getattr(info.sedinte, "DosarSedinta", None)):
        baza_date.actualizeaza_dosar(numar, comp_id, inst_str, obiect_str, stadiu_str, "", ultima_minuta_db_curata or "Fără ședințe publicate")
        return False, None

    sedinte = list(info.sedinte.DosarSedinta)
    sedinte.sort(key=lambda s: str(getattr(s, "data", "") or ""))

    azi = date.today()
    termen_portal = None
    sedinte_viitoare = []
    sedinte_cu_minuta = []

    for s in sedinte:
        d_raw = getattr(s, "data", None)
        sumar = curata_diacritice_portal((getattr(s, "solutieSumar", None) or "").strip())
        sol = curata_diacritice_portal((getattr(s, "solutie", None) or "").strip())
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

    baza_date.actualizeaza_dosar(numar, comp_id, inst_str, obiect_str, stadiu_str, data_sedinta, minuta_curenta)

    if minuta_curenta != ultima_minuta_db_curata or forteaza_reanaliza:
        analiza = analizeaza_cu_claude(
            numar, inst_str, obiect_str, stadiu_str, text_pentru_ai,
            client_nume=client, parti_dosar=parti_str, istoric_sedinte=istoric_scurt,
            nume_cabinet=nume_cabinet
        )
        if isinstance(analiza, dict) and "_eroare" not in analiza:
            if termen_portal and (not analiza.get("noul_termen") or str(analiza.get("noul_termen")).lower() == "null"):
                analiza["noul_termen"] = termen_portal

        if analiza and "_eroare" not in analiza:
            prio_tag = str(analiza.get("prioritate", "IMPORTANT")).upper()
            sarcini_curate = _curata_sarcini_afisare(analiza.get("sarcini_avocat", ""))
            cale_atac_txt = curata_diacritice_portal(analiza.get("cale_atac", ""))
            if cale_atac_txt and cale_atac_txt.lower() not in ("null", "none", "fără cale de atac", "nu este cazul la acest moment"):
                sarcini_extinse = f"[{prio_tag}]\n{sarcini_curate}\n• Cale de atac: {cale_atac_txt}"
            else:
                sarcini_extinse = f"[{prio_tag}]\n{sarcini_curate}"

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
