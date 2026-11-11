import time
import schedule
import baza_date
import app

def executa_rutina_sincronizare():
    timp_curent = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n[CRON] [{timp_curent}] Pornire verificare de fundal Portal Just...")
    
    conn = baza_date.conectare()
    c = conn.cursor()
    c.execute("SELECT id, nume_firma FROM companii")
    companii = c.fetchall()
    conn.close()
    
    total_alerte = 0
    for comp_id, nume_firma in companii:
        try:
            print(f"[CRON] Verificare portofoliu: {nume_firma} (ID: {comp_id})...")
            gasite = app.sincronizeaza_toate_dosarele(comp_id)
            total_alerte += gasite
        except Exception as ex:
            print(f"[EROARE CRON] Compania {nume_firma}: {ex}")
            
    print(f"[CRON] Rutină finalizată. Minute noi procesate & notificate: {total_alerte}\n")

# Orarele cheie când instanțele publică minutele
schedule.every().day.at("13:15").do(executa_rutina_sincronizare)
schedule.every().day.at("17:15").do(executa_rutina_sincronizare)

# Verificare de mentenanță la fiecare 60 de minute
schedule.every(60).minutes.do(executa_rutina_sincronizare)

print("=" * 60)
print("⚡ LexPulse Pro Background Daemon activat cu succes!")
print("Verificări programate zilnic la 13:15 și 17:15 (și la fiecare 60 min).")
print("Minutele neschimbate NU consumă tokeni Claude.")
print("=" * 60)

# Rulăm o primă verificare la inițializare
executa_rutina_sincronizare()

while True:
    schedule.run_pending()
    time.sleep(10)