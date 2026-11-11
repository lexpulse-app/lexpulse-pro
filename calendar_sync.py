import urllib.parse
from datetime import datetime, timedelta

def extrage_data_termen(text_termen):
    if not text_termen or str(text_termen).strip().lower() in ["null", "none", "fără termen stabilit", "-", ""]:
        return None
    cuvinte = text_termen.replace(",", " ").replace(".", " ").replace("/", " ").replace("-", " ").split()
    for i in range(len(cuvinte) - 2):
        try:
            zi = int(cuvinte[i])
            luna = int(cuvinte[i+1])
            an = int(cuvinte[i+2])
            if 1 <= zi <= 31 and 1 <= luna <= 12 and 2024 <= an <= 2030:
                return datetime(an, luna, zi, 9, 0)
        except ValueError:
            continue
    return None

def genereaza_link_google_calendar(numar_dosar, instanta, text_termen, sarcini):
    dt = extrage_data_termen(text_termen)
    if not dt:
        return None
    dt_end = dt + timedelta(hours=2)
    fmt = "%Y%m%dT%H%M%SZ"
    dates = f"{dt.strftime(fmt)}/{dt_end.strftime(fmt)}"
    titlu = f"Termen Judecată: {numar_dosar}"
    detalii = f"Instanță: {instanta}\nTermen: {text_termen}\n\nSarcini / Notițe procedurale:\n{sarcini}"
    
    params = {
        "action": "TEMPLATE",
        "text": titlu,
        "dates": dates,
        "details": detalii,
        "location": instanta
    }
    return f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(params)}"

def genereaza_fisier_ics(numar_dosar, instanta, text_termen, sarcini):
    dt = extrage_data_termen(text_termen)
    if not dt:
        dt = datetime.now() + timedelta(days=1, hours=9)
    dt_end = dt + timedelta(hours=2)
    fmt = "%Y%m%dT%H%M%S"
    
    sarcini_curate = str(sarcini).replace("\n", " ") if sarcini else "Fără sarcini suplimentare"
    
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//LexPulse Pro//RO
CALSCALE:GREGORIAN
BEGIN:VEVENT
SUMMARY:Termen: {numar_dosar} ({instanta})
DESCRIPTION:{sarcini_curate}
LOCATION:{instanta}
DTSTART:{dt.strftime(fmt)}
DTEND:{dt_end.strftime(fmt)}
STATUS:CONFIRMED
BEGIN:VALARM
TRIGGER:-PT24H
ACTION:DISPLAY
DESCRIPTION:Alertă Termen Mâine: {numar_dosar}
END:VALARM
END:VEVENT
END:VCALENDAR"""
    return ics_content.encode("utf-8")