import os
import sqlite3
import bcrypt
from dotenv import load_dotenv

try:
    import streamlit as st
    for k, v in st.secrets.items():
        if isinstance(v, str) and k not in os.environ:
            os.environ[k] = v
except Exception:
    pass

load_dotenv()

try:
    import psycopg2
    from psycopg2 import IntegrityError as PgIntegrityError
except ImportError:
    psycopg2 = None
    PgIntegrityError = Exception

NUME_DB = "asistent_dosare.db"
INTEGRITY_ERRORS = (sqlite3.IntegrityError, PgIntegrityError)


class _CursorWrapper:
    def __init__(self, cursor, is_pg):
        self._cursor = cursor
        self._is_pg = is_pg

    def execute(self, sql, params=None):
        if self._is_pg:
            sql = sql.replace("?", "%s")
        if params is not None:
            return self._cursor.execute(sql, params)
        return self._cursor.execute(sql)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _ConnWrapper:
    def __init__(self, conn, is_pg):
        self._conn = conn
        self._is_pg = is_pg

    def cursor(self):
        return _CursorWrapper(self._conn.cursor(), self._is_pg)

    def commit(self):
        return self._conn.commit()

    def close(self):
        pass  # Pastram conexiunea deschisa in cache pentru viteza maxima

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _get_db_url():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        try:
            import streamlit as st
            url = str(st.secrets.get("DATABASE_URL", "")).strip()
        except Exception:
            pass
    if url.startswith("Postgresql://"):
        url = "postgresql://" + url[len("Postgresql://"):]
    return url


_CACHED_PG_CONN = None

def conectare():
    global _CACHED_PG_CONN
    db_url = _get_db_url()
    if db_url and psycopg2 is not None:
        try:
            if _CACHED_PG_CONN is None or _CACHED_PG_CONN.closed != 0:
                _CACHED_PG_CONN = psycopg2.connect(db_url)
                _CACHED_PG_CONN.autocommit = True
            else:
                with _CACHED_PG_CONN.cursor() as cur:
                    cur.execute("SELECT 1")
            return _ConnWrapper(_CACHED_PG_CONN, True)
        except Exception:
            _CACHED_PG_CONN = psycopg2.connect(db_url)
            _CACHED_PG_CONN.autocommit = True
            return _ConnWrapper(_CACHED_PG_CONN, True)
    return _ConnWrapper(sqlite3.connect(NUME_DB), False)


def hash_parola(parola):
    return bcrypt.hashpw(parola.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verifica_parola(parola_introdusa, hash_stocat):
    return bcrypt.checkpw(parola_introdusa.encode('utf-8'), hash_stocat.encode('utf-8'))


def init_db():
    conn = conectare()
    cursor = conn.cursor()
    is_pg = conn._is_pg

    pk = "SERIAL PRIMARY KEY" if is_pg else "INTEGER PRIMARY KEY AUTOINCREMENT"

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS companii (
        id {pk},
        nume_firma TEXT NOT NULL,
        email_admin TEXT UNIQUE NOT NULL,
        parola_hash TEXT NOT NULL,
        data_inregistrare TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS dosare (
        id {pk},
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

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS alerte (
        id {pk},
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


    # Migrare automata coloane SaaS (multi-tenant + abonamente)
    coloane_noi = [
        ("telegram_chat_id", "TEXT DEFAULT ''"),
        ("plan", "TEXT DEFAULT 'trial'"),
        ("limita_dosare", "INTEGER DEFAULT 2"),
        ("status_abonament", "TEXT DEFAULT 'active'"),
        ("stripe_customer_id", "TEXT DEFAULT ''"),
        ("stripe_subscription_id", "TEXT DEFAULT ''"),
        ("data_expirare", "TEXT DEFAULT ''")
    ]
    for col_nume, col_def in coloane_noi:
        try:
            if is_pg:
                cursor.execute(f"ALTER TABLE companii ADD COLUMN IF NOT EXISTS {col_nume} {col_def}")
            else:
                cursor.execute(f"ALTER TABLE companii ADD COLUMN {col_nume} {col_def}")
        except Exception:
            pass

    # Contul fondatorului are acces nelimitat
    try:
        cursor.execute(
            "UPDATE companii SET plan = 'enterprise', limita_dosare = 9999, status_abonament = 'active' WHERE email_admin = ?",
            ("davidpascu.av@gmail.com",)
        )
    except Exception:
        pass

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
    except INTEGRITY_ERRORS:
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
        return True, "Dosarul a fost introdus cu succes!"
    except INTEGRITY_ERRORS as e:
        err = str(e).lower()
        if "foreign key" in err:
            return False, "Sesiune expirată (compania nu există în baza cloud). Apasă Deconectare și autentifică-te din nou!"
        return False, "Dosarul există deja în monitorizarea cabinetului."
    except Exception as e:
        return False, f"Eroare bază de date: {e}"
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


def sterge_dosar(companie_id, numar_dosar):
    conn = conectare()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alerte WHERE companie_id = ? AND numar_dosar = ?", (companie_id, numar_dosar))
    cursor.execute("DELETE FROM dosare WHERE companie_id = ? AND numar_dosar = ?", (companie_id, numar_dosar))
    conn.commit()
    conn.close()
    return True




def obtine_detalii_companie(companie_id):
    conn = conectare()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, nume_firma, email_admin, COALESCE(telegram_chat_id, ''), 
               COALESCE(plan, 'trial'), COALESCE(limita_dosare, 2), 
               COALESCE(status_abonament, 'active'), COALESCE(data_expirare, '')
        FROM companii WHERE id = ?
    """, (companie_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "nume_firma": row[1],
        "email": row[2],
        "telegram_chat_id": row[3], "email_notificari": row[4] if len(row) > 4 else "",
        "plan": row[4],
        "limita_dosare": int(row[5] or 2),
        "status_abonament": row[6],
        "data_expirare": row[7]
    }


def actualizeaza_telegram_companie(companie_id, chat_id):
    conn = conectare()
    cursor = conn.cursor()
    cursor.execute("UPDATE companii SET telegram_chat_id = ? WHERE id = ?", (str(chat_id).strip(), companie_id))
    conn.commit()
    conn.close()


def activeaza_plan_companie(companie_id, plan, limita_dosare, stripe_customer_id="", data_expirare="", stripe_subscription_id=""):
    conn = conectare()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE companii 
        SET plan = ?, limita_dosare = ?, status_abonament = 'active', 
            stripe_customer_id = ?, stripe_subscription_id = ?, data_expirare = ?
        WHERE id = ?
    """, (plan, limita_dosare, stripe_customer_id, stripe_subscription_id, data_expirare, companie_id))
    conn.commit()
    conn.close()


def verifica_limita_dosare(companie_id):
    det = obtine_detalii_companie(companie_id) or {}
    if det.get("plan") == "expirat" or int(det.get("limita_dosare", 0)) <= 0:
        return False, 0, 0
    info = obtine_detalii_companie(companie_id)
    if not info:
        return False, 0, 0
    conn = conectare()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM dosare WHERE activ = 1 AND companie_id = ?", (companie_id,))
    nr_curent = cursor.fetchone()[0]
    conn.close()
    limita = info["limita_dosare"]
    return nr_curent < limita, nr_curent, limita


if __name__ == "__main__":
    init_db()


def obtine_utilizator_dupa_email(email: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT u.id, u.email, u.nume_complet, u.companie_id, comp.nume_cabinet
        FROM utilizatori u
        JOIN companii comp ON u.companie_id = comp.id
        WHERE LOWER(u.email) = LOWER(?)
    """, (email.strip(),))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "email": row[1], "nume_complet": row[2], "companie_id": row[3], "nume_cabinet": row[4]}


def dezactiveaza_abonament_expirat(companie_id: int):
    conn = conectare()
    c = conn.cursor()
    c.execute(
        "UPDATE companii SET plan = 'expirat', limita_dosare = 0, status_abonament = 'expired' WHERE id = ?",
        (companie_id,)
    )
    conn.commit()
    conn.close()

def obtine_subscription_id_companie(companie_id: int) -> str:
    conn = conectare()
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE companii ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT")
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    c.execute("SELECT stripe_subscription_id FROM companii WHERE id = ?", (companie_id,))
    row = c.fetchone()
    conn.close()
    return (row[0] or "").strip() if row else ""

def actualizeaza_email_companie(companie_id: int, email_notificari: str):
    conn = conectare()
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE companii ADD COLUMN IF NOT EXISTS email_notificari TEXT")
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    c.execute("UPDATE companii SET email_notificari = ? WHERE id = ?", (email_notificari.strip(), companie_id))
    conn.commit()
    conn.close()
