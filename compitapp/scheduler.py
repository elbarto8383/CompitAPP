import os
from datetime import date, datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from argo_client import (get_studenti, fetch_compiti, fetch_voti, fetch_assenze,
                         fetch_note, fetch_bacheca, fetch_argomenti, fetch_promemoria)
from models import get_db
from notifier import (notifica_nuovi_compiti, notifica_nuovo_voto, notifica_assenza,
                      notifica_nota, notifica_bacheca, notifica_promemoria,
                      reminder_compiti_domani, sync_sensori_ha)

TZ = pytz.timezone('Europe/Rome')
ORARIO_REMINDER = os.environ.get('ORARIO_REMINDER', '20:00')
POLLING_MINUTI = int(os.environ.get('POLLING_MINUTI', 30))

def _esiste(conn, tabella, studente, **kwargs):
    where = ' AND '.join([f"{k}=?" for k in kwargs.keys()])
    vals = [studente] + list(kwargs.values())
    return conn.execute(
        f'SELECT id FROM {tabella} WHERE studente=? AND {where}', vals
    ).fetchone() is not None

def sync_compiti():
    print(f"[SCHEDULER] Sync compiti — {datetime.now().strftime('%H:%M:%S')}")
    for studente in get_studenti():
        nome = studente.get('nome', 'Studente')
        try:
            compiti_raw = fetch_compiti(studente)
            if not compiti_raw:
                continue
            conn = get_db()
            nuovi = {}
            tot_trovati = 0
            for data_str, info in compiti_raw.items():
                for materia, testo in zip(info.get('materie',[]), info.get('compiti',[])):
                    testo_clean = testo.strip()
                    tot_trovati += 1
                    if not _esiste(conn, 'compiti', nome, data=data_str, materia=materia, testo=testo_clean[:500]):
                        conn.execute('INSERT INTO compiti (studente,data,materia,testo) VALUES (?,?,?,?)',
                                     (nome, data_str, materia, testo_clean[:1000]))
                        print(f"[SCHEDULER] 🆕 Nuovo compito {nome}: {materia} per {data_str}")
                        try:
                            if datetime.strptime(data_str, '%Y-%m-%d').date() >= date.today():
                                nuovi.setdefault(data_str, {'materie':[], 'compiti':[]})
                                nuovi[data_str]['materie'].append(materia)
                                nuovi[data_str]['compiti'].append(testo_clean)
                        except Exception:
                            pass
            conn.commit()
            conn.close()
            print(f"[SCHEDULER] Compiti {nome}: {tot_trovati} trovati, {sum(len(v['materie']) for v in nuovi.values())} nuovi")
            if nuovi:
                notifica_nuovi_compiti(nome, nuovi)
            else:
                print(f"[SCHEDULER] Nessun compito nuovo per {nome}")
            _aggiorna_sensori(nome)
        except Exception as e:
            print(f"[SCHEDULER] Errore compiti {nome}: {e}")

def sync_voti():
    print(f"[SCHEDULER] Sync voti — {datetime.now().strftime('%H:%M:%S')}")
    for studente in get_studenti():
        nome = studente.get('nome', 'Studente')
        try:
            voti_raw = fetch_voti(studente)
            if not voti_raw:
                continue
            conn = get_db()
            for v in voti_raw:
                data_str = v.get('data','')
                materia = v.get('materia','')
                valore = str(v.get('voto',''))
                desc = v.get('descrizione','')
                if data_str and materia and valore:
                    if not _esiste(conn, 'voti', nome, data=data_str, materia=materia, voto=valore):
                        conn.execute('INSERT INTO voti (studente,data,materia,voto,descrizione) VALUES (?,?,?,?,?)',
                                     (nome, data_str, materia, valore, desc))
                        notifica_nuovo_voto(nome, materia, valore, desc)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SCHEDULER] Errore voti {nome}: {e}")

def sync_assenze():
    print(f"[SCHEDULER] Sync assenze — {datetime.now().strftime('%H:%M:%S')}")
    for studente in get_studenti():
        nome = studente.get('nome', 'Studente')
        try:
            assenze_raw = fetch_assenze(studente)
            if not assenze_raw:
                continue
            conn = get_db()
            for a in assenze_raw:
                data_str = a.get('data','')
                tipo = a.get('tipo','A')
                desc = a.get('descrizione','')
                giust = 1 if a.get('giustificata') else 0
                if data_str and tipo:
                    if not _esiste(conn, 'assenze', nome, data=data_str, tipo=tipo):
                        conn.execute('INSERT INTO assenze (studente,data,tipo,descrizione,giustificata) VALUES (?,?,?,?,?)',
                                     (nome, data_str, tipo, desc, giust))
                        notifica_assenza(nome, data_str, tipo)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SCHEDULER] Errore assenze {nome}: {e}")

def sync_note():
    for studente in get_studenti():
        nome = studente.get('nome', 'Studente')
        try:
            note_raw = fetch_note(studente)
            if not note_raw:
                continue
            conn = get_db()
            for n in note_raw:
                data_str = n.get('data','')
                testo = n.get('testo','')
                docente = n.get('docente','')
                if data_str and testo:
                    if not _esiste(conn, 'note_disciplinari', nome, data=data_str, testo=testo[:200]):
                        conn.execute('INSERT INTO note_disciplinari (studente,data,docente,testo) VALUES (?,?,?,?)',
                                     (nome, data_str, docente, testo))
                        notifica_nota(nome, data_str, docente, testo)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SCHEDULER] Errore note {nome}: {e}")

def sync_bacheca():
    print(f"[SCHEDULER] Sync bacheca — {datetime.now().strftime('%H:%M:%S')}")
    for studente in get_studenti():
        nome = studente.get('nome', 'Studente')
        try:
            bacheca_raw = fetch_bacheca(studente)
            if not bacheca_raw:
                continue
            conn = get_db()
            for msg in bacheca_raw:
                uid = msg.get('uid','')
                titolo = msg.get('titolo','')
                testo = msg.get('testo','')
                mittente = msg.get('mittente','')
                data_str = msg.get('data','')
                if titolo:
                    # Usa uid come chiave univoca se disponibile, altrimenti titolo+data
                    exists = False
                    if uid:
                        exists = conn.execute('SELECT id FROM bacheca WHERE uid=?', (uid,)).fetchone() is not None
                    else:
                        exists = _esiste(conn, 'bacheca', nome, titolo=titolo[:200], data=data_str)
                    if not exists:
                        conn.execute('INSERT INTO bacheca (studente,data,titolo,testo,mittente,uid) VALUES (?,?,?,?,?,?)',
                                     (nome, data_str, titolo[:500], testo[:2000], mittente, uid))
                        notifica_bacheca(nome, titolo, testo, mittente)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SCHEDULER] Errore bacheca {nome}: {e}")

def sync_argomenti():
    for studente in get_studenti():
        nome = studente.get('nome', 'Studente')
        try:
            args_raw = fetch_argomenti(studente)
            if not args_raw:
                continue
            conn = get_db()
            for a in args_raw:
                data_str = a.get('data','')
                materia = a.get('materia','')
                argomento = a.get('argomento','')
                attivita = a.get('attivita','')
                if data_str and (argomento or attivita):
                    if not _esiste(conn, 'argomenti', nome, data=data_str, materia=materia, argomento=argomento[:200]):
                        conn.execute('INSERT INTO argomenti (studente,data,materia,argomento,attivita) VALUES (?,?,?,?,?)',
                                     (nome, data_str, materia, argomento[:500], attivita[:500]))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SCHEDULER] Errore argomenti {nome}: {e}")

def sync_promemoria():
    for studente in get_studenti():
        nome = studente.get('nome', 'Studente')
        try:
            prom_raw = fetch_promemoria(studente)
            if not prom_raw:
                continue
            conn = get_db()
            for p in prom_raw:
                data_str = p.get('data','')
                testo = p.get('testo','')
                docente = p.get('docente','')
                if data_str and testo:
                    if not _esiste(conn, 'promemoria', nome, data=data_str, testo=testo[:200]):
                        conn.execute('INSERT INTO promemoria (studente,data,testo,docente) VALUES (?,?,?,?)',
                                     (nome, data_str, testo[:500], docente))
                        notifica_promemoria(nome, data_str, docente, testo)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SCHEDULER] Errore promemoria {nome}: {e}")

def sync_tutto():
    """Sync completo di tutto"""
    sync_compiti()
    sync_voti()
    sync_assenze()
    sync_note()
    sync_bacheca()
    sync_argomenti()
    sync_promemoria()

def reminder_sera():
    print("[SCHEDULER] Reminder serale")
    domani = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    for studente in get_studenti():
        nome = studente.get('nome', 'Studente')
        try:
            conn = get_db()
            rows = conn.execute('SELECT materia, testo FROM compiti WHERE studente=? AND data=? ORDER BY materia', (nome, domani)).fetchall()
            conn.close()
            compiti_domani = {'materie':[r['materia'] for r in rows], 'compiti':[r['testo'] for r in rows]} if rows else None
            reminder_compiti_domani(nome, compiti_domani)
        except Exception as e:
            print(f"[SCHEDULER] Errore reminder {nome}: {e}")

def _aggiorna_sensori(nome):
    try:
        oggi = date.today().strftime('%Y-%m-%d')
        domani = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        conn = get_db()
        n_oggi   = conn.execute('SELECT COUNT(*) as n FROM compiti WHERE studente=? AND data=?', (nome, oggi)).fetchone()['n']
        n_domani = conn.execute('SELECT COUNT(*) as n FROM compiti WHERE studente=? AND data=?', (nome, domani)).fetchone()['n']
        n_assenze = conn.execute('SELECT COUNT(*) as n FROM assenze WHERE studente=?', (nome,)).fetchone()['n']
        n_bacheca = conn.execute('SELECT COUNT(*) as n FROM bacheca WHERE studente=? AND notificato=0', (nome,)).fetchone()['n']
        ultimo_voto = conn.execute('SELECT voto, materia FROM voti WHERE studente=? ORDER BY data DESC, id DESC LIMIT 1', (nome,)).fetchone()
        tutti_voti = conn.execute('SELECT voto FROM voti WHERE studente=?', (nome,)).fetchall()
        conn.close()
        valori = []
        for v in tutti_voti:
            try:
                valori.append(float(str(v['voto']).replace(',','.')))
            except Exception:
                pass
        media = round(sum(valori)/len(valori), 1) if valori else 'N/D'
        sync_sensori_ha(nome, {
            'compiti_oggi': n_oggi, 'compiti_domani': n_domani,
            'assenze_totali': n_assenze, 'bacheca_non_lette': n_bacheca,
            'ultimo_voto': ultimo_voto['voto'] if ultimo_voto else 'N/D',
            'ultima_materia': ultimo_voto['materia'] if ultimo_voto else '',
            'media_voti': media
        })
    except Exception as e:
        print(f"[SCHEDULER] Errore sensori {nome}: {e}")

def heartbeat():
    """Log ogni 5 minuti per verificare che lo scheduler giri"""
    from datetime import datetime
    print(f"[SCHEDULER] ❤️ Heartbeat — {datetime.now().strftime('%H:%M:%S')}")

def avvia_scheduler():
    scheduler = BackgroundScheduler(timezone=TZ)
    scheduler.add_job(sync_tutto, 'interval', minutes=POLLING_MINUTI, id='sync_tutto')
    scheduler.add_job(heartbeat, 'interval', minutes=5, id='heartbeat')
    try:
        ora, minuto = ORARIO_REMINDER.split(':')
        scheduler.add_job(reminder_sera, CronTrigger(hour=int(ora), minute=int(minuto)), id='reminder_sera')
    except Exception:
        scheduler.add_job(reminder_sera, CronTrigger(hour=20, minute=0), id='reminder_sera')
    scheduler.start()
    print(f"[SCHEDULER] Avviato — polling ogni {POLLING_MINUTI} min, reminder alle {ORARIO_REMINDER}")
    sync_tutto()
    return scheduler
