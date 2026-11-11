import zeep

# Adresa oficiala publica prin care Ministerul Justitiei ofera date despre dosare
URL_WSDL = "http://portalquery.just.ro/query.asmx?WSDL"

def obtine_date_dosar(numar_dosar):
    print(f"Se interogheaza portal.just.ro pentru dosarul: {numar_dosar}...")
    
    # Initializam clientul SOAP care stie sa comunice cu serverul instantei
    client = zeep.Client(wsdl=URL_WSDL)
    
    # Trimitem interogarea prin functia CautareDosare2 pusa la dispozitie de minister
    rezultate = client.service.CautareDosare2(
        numarDosar=numar_dosar,
        obiectDosar=None,
        numeParte=None,
        institutie=None,
        dataStart=None,
        dataStop=None
    )
    
    if not rezultate:
        print("Nu a fost gasit niciun dosar cu acest numar.")
        return

    # Luam primul dosar identificat
    dosar = rezultate[0]
    print("\n--- DATE DOSAR GASIT ---")
    print(f"Numar dosar: {dosar.numar}")
    print(f"Institutie: {dosar.institutie}")
    print(f"Stadiu procesual: {dosar.stadiuProcesualNume}")
    print(f"Obiect: {dosar.obiect}")

    # Verificam sedintele de judecata si minutele
    if dosar.sedinte and dosar.sedinte.DosarSedinta:
        sedinte = dosar.sedinte.DosarSedinta
        ultima_sedinta = sedinte[-1] # Ultima sedinta inregistrata
        
        print("\n--- ULTIMUL TERMEN / SEDINTA ---")
        print(f"Data sedintei: {ultima_sedinta.data}")
        print(f"Ora: {ultima_sedinta.ora}")
        print(f"Solutie pe scurt: {ultima_sedinta.solutieSumar}")
    else:
        print("\nNu exista sedinte inregistrate inca pentru acest dosar.")

# Testam cu un dosar public existent (exemplu: Tribunalul Bucuresti)
if __name__ == "__main__":
    dosar_test = "1234/2/2024"
    obtine_date_dosar(dosar_test)
    