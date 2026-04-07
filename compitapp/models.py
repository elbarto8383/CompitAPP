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

    conn.commit()
    conn.close()
    print("[DB] Inizializzato correttamente")
