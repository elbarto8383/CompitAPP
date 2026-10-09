import sqlite3
import os

DB_PATH = os.environ.get('DB_PATH', '/data/compitapp.db')

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS compiti (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        studente TEXT NOT NULL DEFAULT 'default',
        data TEXT NOT NULL, materia TEXT NOT NULL, testo TEXT NOT NULL,
        notificato INTEGER DEFAULT 0,
        creato_il TEXT DEFAULT (datetime('now','localtime'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS voti (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        studente TEXT NOT NULL DEFAULT 'default',
        data TEXT NOT NULL, materia TEXT NOT NULL, voto TEXT NOT NULL,
        descrizione TEXT, notificato INTEGER DEFAULT 0,
        creato_il TEXT DEFAULT (datetime('now','localtime'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS assenze (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        studente TEXT NOT NULL DEFAULT 'default',
        data TEXT NOT NULL, tipo TEXT NOT NULL,
        descrizione TEXT, giustificata INTEGER DEFAULT 0,
        notificato INTEGER DEFAULT 0,
        creato_il TEXT DEFAULT (datetime('now','localtime'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS note_disciplinari (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        studente TEXT NOT NULL DEFAULT 'default',
        data TEXT NOT NULL, docente TEXT, testo TEXT,
        notificato INTEGER DEFAULT 0,
        creato_il TEXT DEFAULT (datetime('now','localtime'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS bacheca (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        studente TEXT NOT NULL DEFAULT 'default',
        data TEXT, titolo TEXT, testo TEXT, mittente TEXT, uid TEXT UNIQUE,
        notificato INTEGER DEFAULT 0,
        creato_il TEXT DEFAULT (datetime('now','localtime'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS argomenti (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        studente TEXT NOT NULL DEFAULT 'default',
        data TEXT NOT NULL, materia TEXT, argomento TEXT, attivita TEXT,
        creato_il TEXT DEFAULT (datetime('now','localtime'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS promemoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        studente TEXT NOT NULL DEFAULT 'default',
        data TEXT NOT NULL, testo TEXT, docente TEXT,
        notificato INTEGER DEFAULT 0,
        creato_il TEXT DEFAULT (datetime('now','localtime'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS meta (
        chiave TEXT PRIMARY KEY, valore TEXT,
        aggiornato_il TEXT DEFAULT (datetime('now','localtime'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS lezioni_registro (
        studente TEXT NOT NULL DEFAULT 'default',
        data TEXT NOT NULL, ora INTEGER NOT NULL,
        materia TEXT NOT NULL, docente TEXT,
        PRIMARY KEY (studente, data, ora, materia)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS orario (
        studente TEXT NOT NULL DEFAULT 'default',
        giorno INTEGER NOT NULL, ora INTEGER NOT NULL,
        materia TEXT NOT NULL, docente TEXT,
        aggiornato_il TEXT DEFAULT (datetime('now','localtime')),
        PRIMARY KEY (studente, giorno, ora)
    )''')

    conn.commit()
    conn.close()
    print("[DB] Inizializzato correttamente")


def _num(v):
    """Numero da un valore Argo (8.15, "8,15", "8.15"); None se assente, non numerico o 0."""
    if v in (None, ''):
        return None
    try:
        n = round(float(str(v).replace(',', '.')), 2)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def media_argo(conn, nome):
    """Medie calcolate da Argo (salvate dallo scheduler): {'generale': float|None, 'materie': {materia: float}}.
    Sono le stesse dell'app DiDUP: escludono già i voti «non fa media». None se non disponibili."""
    import json
    r = conn.execute('SELECT valore FROM meta WHERE chiave=?', (f"media_argo:{nome}",)).fetchone()
    if not r:
        return None
    try:
        d = json.loads(r['valore'])
    except Exception:
        return None
    materie = {m: _num(v) for m, v in (d.get('materie') or {}).items()}
    materie = {m: v for m, v in materie.items() if v is not None}
    generale = _num(d.get('generale'))
    if generale is None and not materie:
        return None
    return {'generale': generale, 'materie': materie}


def svuota_studente(conn, nome):
    """Cancella tutti i dati salvati di uno studente e i segni di «storico già caricato»,
    così al prossimo giro l'anno scolastico viene riletto da capo (senza notifiche)."""
    for t in ('compiti', 'voti', 'assenze', 'note_disciplinari', 'bacheca',
              'argomenti', 'promemoria', 'orario', 'lezioni_registro'):
        conn.execute(f'DELETE FROM {t} WHERE studente=?', (nome,))
    conn.execute("DELETE FROM meta WHERE chiave LIKE ? OR chiave = ?",
                 (f"storico:%:{nome}", f"media_argo:{nome}"))
