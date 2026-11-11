import sqlite3
import bcrypt

NUME_DB = "asistent_dosare.db"

def conectare():
    return sqlite3.connect(NUME_DB)

def hash_parola(parola):
    return bcrypt.hashpw(parola.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verifica_parola(parola_introdusa, hash_stocat):
    return bcrypt.checkpw(parola_introdusa.encode('utf-8'), hash_stocat.encode('utf-8'))

def init_db():
    conn = conectare()
    cursor = conn.cursor()
    
    # Tabel organizații / firme de avocatură
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS companii (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nume_firma TEXT NOT NULL,
        email_admin TEXT UNIQUE NOT NULL,
        parola_hash TEXT NOT NULL,
        data_inregistrare TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Tabel dosare asociate fiecărei firme
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dosare (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        companie_id INTEGER NOT NULL,
        numar_dosar TEXT NOT NULL,
        nume_client TEXT,
        contact_client TEXT,
        institutie TEXT,
        obiect TEXT,
        stadiu TEXT,
        ultima_data_sedinta TEXT,
        ultima_minuta TEXT,
        activ INTEGER DEFAULT 1,
        UNIQUE(companie_id, numar_dosar),
        FOREIGN KEY (companie_id) REFERENCES companii(id)
    )
    """)
    
    # Tabel alerte
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerte (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        companie_id INTEGER NOT NULL,
        numar_dosar TEXT NOT NULL,
        data_adaugare TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        tip_solutie TEXT,
        noul_termen TEXT,
        sarcini_avocat TEXT,
        mesaj_client TEXT,
        FOREIGN KEY (companie_id) REFERENCES companii(id)
    )
    """)
    
    conn.commit()
    conn.close()

def inregistreaza_companie(nume_firma, email, parola):
    conn = conectare()
    cursor = conn.cursor()
    try:
        parola_h = hash_parola(parola)
        cursor.execute("""
        INSERT INTO companii (nume_firma, email_admin, parola_hash)
        VALUES (?, ?, ?)
        """, (nume_firma.strip(), email.strip().lower(), parola_h))
        conn.commit()
        return True, "Contul a fost creat cu succes!"
    except sqlite3.IntegrityError:
        return False, "Există deja un cont înregistrat cu acest email."
    finally:
        conn.close()

def autentifica_utilizator(email, parola):
    conn = conectare()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nume_firma, parola_hash FROM companii WHERE email_admin = ?", (email.strip().lower(),))
    row = cursor.fetchone()
    conn.close()
    
    if row and verifica_parola(parola, row[2]):
        return {"id": row[0], "nume_firma": row[1], "email": email}
    return None

def adauga_dosar(companie_id, numar_dosar, nume_client="", contact_client=""):
    conn = conectare()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO dosare (companie_id, numar_dosar, nume_client, contact_client)
        VALUES (?, ?, ?, ?)
        """, (companie_id, numar_dosar.strip(), nume_client.strip(), contact_client.strip()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def obtine_dosare_active(companie_id=None):
    conn = conectare()
    cursor = conn.cursor()
    if companie_id:
        cursor.execute("""
        SELECT id, numar_dosar, nume_client, contact_client, ultima_minuta, companie_id 
        FROM dosare WHERE activ = 1 AND companie_id = ?
        """, (companie_id,))
    else:
        cursor.execute("""
        SELECT id, numar_dosar, nume_client, contact_client, ultima_minuta, companie_id 
        FROM dosare WHERE activ = 1
        """)
    randuri = cursor.fetchall()
    conn.close()
    return randuri

def actualizeaza_dosar(numar_dosar, companie_id, institutie, obiect, stadiu, data_sedinta, minuta):
    conn = conectare()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE dosare 
    SET institutie = ?, obiect = ?, stadiu = ?, ultima_data_sedinta = ?, ultima_minuta = ?
    WHERE numar_dosar = ? AND companie_id = ?
    """, (institutie, obiect, stadiu, data_sedinta, minuta, numar_dosar, companie_id))
    conn.commit()
    conn.close()

def salveaza_alerta(companie_id, numar_dosar, tip_solutie, noul_termen, sarcini, mesaj):
    conn = conectare()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO alerte (companie_id, numar_dosar, tip_solutie, noul_termen, sarcini_avocat, mesaj_client)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (companie_id, numar_dosar, tip_solutie, noul_termen, sarcini, mesaj))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()