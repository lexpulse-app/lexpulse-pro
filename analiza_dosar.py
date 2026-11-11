import os
import zeep
from dotenv import load_dotenv
from anthropic import Anthropic

# Incarcam cheia din fisierul .env
load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")

if not api_key:
    raise ValueError("Eroare: Nu a fost gasita cheia ANTHROPIC_API_KEY in fisierul .env!")

# Initializam Claude
client_ai = Anthropic(api_key=api_key)

URL_WSDL = "http://portalquery.just.ro/query.asmx?WSDL"

def extrage_si_analizeaza(numar_dosar):
    print(f"\n[1/2] Se descarca datele din Portal Just pentru: {numar_dosar}...")
    
    # 1. Preluarea datelor de pe Portal Just
    client_soap = zeep.Client(wsdl=URL_WSDL)
    rezultate = client_soap.service.CautareDosare2(
        numarDosar=numar_dosar,
        obiectDosar=None,
        numeParte=None,
        institutie=None,
        dataStart=None,
        dataStop=None
    )
    
    if not rezultate:
        print("Dosarul nu a fost gasit.")
        return

    dosar = rezultate[0]
    institutie = dosar.institutie
    obiect = dosar.obiect
    stadiu = dosar.stadiuProcesualNume

    if not (dosar.sedinte and dosar.sedinte.DosarSedinta):
        print("Dosarul nu are sedinte inregistrate.")
        return

    ultima_sedinta = dosar.sedinte.DosarSedinta[-1]
    data_sedintei = ultima_sedinta.data
    minuta_bruta = ultima_sedinta.solutieSumar

    print(f"[Portal Just] Sedinta: {data_sedintei}")
    print(f"[Portal Just] Minuta: {minuta_bruta}")

    if not minuta_bruta:
        print("Nu exista solutie publicata inca pentru aceasta sedinta.")
        return

    # 2. Transmiterea catre Claude pentru analiza juridica
    print("\n[2/2] Claude analizeaza minuta si genereaza raportul...")

    prompt = f"""
Ești un asistent juridic de elită pentru instanțele din România.
Analizează următoarele detalii ale unui dosar:
- Număr dosar: {numar_dosar}
- Instanță: {institutie}
- Obiect: {obiect}
- Stadiu procesual: {stadiu}
- Minută instanță: {minuta_bruta}

Te rog să generezi un răspuns clar structurat exact după următoarele puncte:
1. TIPUL SOLUȚIEI: (ex: amânare de pronunțare, amânarea judecății cauzei, admitere acțiune, respingere etc.)
2. NOUL TERMEN / DATA PRONUNȚĂRII: (data exactă extrasă sau mențiunea dacă lipsește)
3. CALEA DE ATAC ȘI TERMENUL: (termenul menționat în minută sau aplicabil dacă e specificat)
4. SARCINI PENTRU AVOCAT: (ce măsuri procedurale sau de calendar intern trebuie luate)
5. RAPORT PENTRU CLIENT: (un mesaj profesional, redactat clar și empatic, gata de trimis pe WhatsApp/email, prin care clientul este informat cu privire la ce s-a întâmplat)
"""

    raspuns = client_ai.messages.create(
        model="claude-haiku-5-5",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    print("\n================== RAPORT GENERAT DE CLAUDE ==================")
    print(raspuns.content[0].text)
    print("==============================================================")

if __name__ == "__main__":
    # Testam cu dosarul de la Curtea de Apel Bucuresti
    dosar_exemplu = "1234/2/2024"
    extrage_si_analizeaza(dosar_exemplu)