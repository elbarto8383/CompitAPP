import os
from datetime import date, datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from argo_client import (get_studenti, fetch_dashboard, fetch_compiti, fetch_voti, fetch_assenze,
                         fetch_note, fetch_bacheca, fetch_argomenti, fetch_promemoria,
                         fetch_orario, fetch_registro)
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

def _giorni_da_inizio_anno():
    """Giorni dall'inizio dell'anno scolastico (1 settembre), con un piccolo margine"""
    oggi = date.today()
    inizio = date(oggi.year if oggi.month >= 9 else oggi.year - 1, 9, 1)
    return min((oggi - inizio).days + 7, 400)

def _prepara(studente, categoria):
    """Finestra di lettura per una categoria di dati.
    La prima volta (e finché Argo non risponde) si legge tutto l'anno scolastico e SENZA notifiche:
    la richiesta standard restituisce solo le novità di oggi, quindi voti, assenze e comunicazioni
    precedenti all'installazione non arrivavano mai. Poi bastano gli ultimi giorni.
    Ritorna (giorni, silenzioso), oppure None se Argo non è raggiungibile."""
    nome = studente.get('nome', 'Studente')
    conn = get_db()
    fatto = conn.execute('SELECT 1 FROM meta WHERE chiave=?', (f"storico:{categoria}:{nome}",)).fetchone() is not None
    conn.close()
    giorni, silenzioso = (7, False) if fatto else (_giorni_da_inizio_anno(), True)
    if fetch_dashboard(studente, giorni) is None:
        return None
    return giorni, silenzioso

def _storico_fatto(conn, categoria, nome):
    conn.execute("INSERT OR REPLACE INTO meta (chiave, valore) VALUES (?, '1')", (f"storico:{categoria}:{nome}",))

def sync_voti():
    print(f"[SCHEDULER] Sync voti — {datetime.now().strftime('%H:%M:%S')}")
    for studente in get_studenti():
        nome = studente.get('nome', 'Studente')
        try:
            prep = _prepara(studente, 'voti')
            if prep is None:
                continue
            giorni, silenzioso = prep
            conn = get_db()
            nuovi = 0
            # pulizia: vecchie annotazioni senza voto salvate da versioni precedenti
            conn.execute("DELETE FROM voti WHERE studente=? AND voto IN ('0','0.0','0,0','N')", (nome,))
            voti_raw = fetch_voti(studente, giorni)
            print(f"[SCHEDULER] Voti {nome}: {len(voti_raw)} ricevuti da Argo (ultimi {giorni} giorni)")
            for v in voti_raw:
                data_str = v.get('data','')
                materia = v.get('materia','')
                valore = str(v.get('voto',''))
                desc = v.get('descrizione','')
                if data_str and materia and valore:
                    if not _esiste(conn, 'voti', nome, data=data_str, materia=materia, voto=valore):
                        conn.execute('INSERT INTO voti (studente,data,materia,voto,descrizione,notificato) VALUES (?,?,?,?,?,?)',
                                     (nome, data_str, materia, valore, desc, 1 if silenzioso else 0))
                        nuovi += 1
                        if not silenzioso:
                            notifica_nuovo_voto(nome, materia, valore, desc)
            if silenzioso:
                _storico_fatto(conn, 'voti', nome)
                print(f"[SCHEDULER] Voti {nome}: caricato lo storico ({nuovi} voti), senza notifiche")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SCHEDULER] Errore voti {nome}: {e}")

def sync_assenze():
    print(f"[SCHEDULER] Sync assenze — {datetime.now().strftime('%H:%M:%S')}")
    for studente in get_studenti():
        nome = studente.get('nome', 'Studente')
        try:
            prep = _prepara(studente, 'assenze')
            if prep is None:
                continue
            giorni, silenzioso = prep
            conn = get_db()
            nuovi = 0
            assenze_raw = fetch_assenze(studente, giorni)
            print(f"[SCHEDULER] Assenze {nome}: {len(assenze_raw)} ricevute da Argo (ultimi {giorni} giorni)")
            for a in assenze_raw:
                data_str = a.get('data','')
                tipo = a.get('tipo','A')
                desc = a.get('descrizione','')
                giust = 1 if a.get('giustificata') else 0
                if data_str and tipo:
                    if not _esiste(conn, 'assenze', nome, data=data_str, tipo=tipo):
                        conn.execute('INSERT INTO assenze (studente,data,tipo,descrizione,giustificata,notificato) VALUES (?,?,?,?,?,?)',
                                     (nome, data_str, tipo, desc, giust, 1 if silenzioso else 0))
                        nuovi += 1
                        if not silenzioso:
                            notifica_assenza(nome, data_str, tipo)
            if silenzioso:
                _storico_fatto(conn, 'assenze', nome)
                print(f"[SCHEDULER] Assenze {nome}: caricato lo storico ({nuovi}), senza notifiche")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SCHEDULER] Errore assenze {nome}: {e}")

def sync_note():
    for studente in get_studenti():
        nome = studente.get('nome', 'Studente')
        try:
            prep = _prepara(studente, 'note')
            if prep is None:
                continue
            giorni, silenzioso = prep
            conn = get_db()
            for n in fetch_note(studente, giorni):
                data_str = n.get('data','')
                testo = n.get('testo','')
                docente = n.get('docente','')
                if data_str and testo:
                    if not _esiste(conn, 'note_disciplinari', nome, data=data_str, testo=testo[:200]):
                        conn.execute('INSERT INTO note_disciplinari (studente,data,docente,testo,notificato) VALUES (?,?,?,?,?)',
                                     (nome, data_str, docente, testo, 1 if silenzioso else 0))
                        if not silenzioso:
                            notifica_nota(nome, data_str, docente, testo)
            if silenzioso:
                _storico_fatto(conn, 'note', nome)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SCHEDULER] Errore note {nome}: {e}")

def sync_bacheca():
    print(f"[SCHEDULER] Sync bacheca — {datetime.now().strftime('%H:%M:%S')}")
    for studente in get_studenti():
        nome = studente.get('nome', 'Studente')
        try:
            prep = _prepara(studente, 'bacheca')
            if prep is None:
                continue
            giorni, silenzioso = prep
            conn = get_db()
            nuovi = 0
            bacheca_raw = fetch_bacheca(studente, giorni)
            print(f"[SCHEDULER] Bacheca {nome}: {len(bacheca_raw)} ricevute da Argo (ultimi {giorni} giorni)")
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
                        conn.execute('INSERT INTO bacheca (studente,data,titolo,testo,mittente,uid,notificato) VALUES (?,?,?,?,?,?,?)',
                                     (nome, data_str, titolo[:500], testo[:2000], mittente, uid, 1 if silenzioso else 0))
                        nuovi += 1
                        if not silenzioso:
                            notifica_bacheca(nome, titolo, testo, mittente)
            if silenzioso:
                _storico_fatto(conn, 'bacheca', nome)
                print(f"[SCHEDULER] Bacheca {nome}: caricato lo storico ({nuovi}), senza notifiche")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SCHEDULER] Errore bacheca {nome}: {e}")

def sync_argomenti():
    for studente in get_studenti():
        nome = studente.get('nome', 'Studente')
        try:
            prep = _prepara(studente, 'argomenti')
            if prep is None:
                continue
            giorni, silenzioso = prep
            conn = get_db()
            for a in fetch_argomenti(studente, giorni):
                data_str = a.get('data','')
                materia = a.get('materia','')
                argomento = a.get('argomento','')
                attivita = a.get('attivita','')
                if data_str and (argomento or attivita):
                    if not _esiste(conn, 'argomenti', nome, data=data_str, materia=materia, argomento=argomento[:200]):
                        conn.execute('INSERT INTO argomenti (studente,data,materia,argomento,attivita) VALUES (?,?,?,?,?)',
                                     (nome, data_str, materia, argomento[:500], attivita[:500]))
            if silenzioso:
                _storico_fatto(conn, 'argomenti', nome)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SCHEDULER] Errore argomenti {nome}: {e}")

def sync_promemoria():
    for studente in get_studenti():
        nome = studente.get('nome', 'Studente')
        try:
            prep = _prepara(studente, 'promemoria')
            if prep is None:
                continue
            giorni, silenzioso = prep
            conn = get_db()
            for p in fetch_promemoria(studente, giorni):
                data_str = p.get('data','')
                testo = p.get('testo','')
                docente = p.get('docente','')
                if data_str and testo:
                    if not _esiste(conn, 'promemoria', nome, data=data_str, testo=testo[:200]):
                        conn.execute('INSERT INTO promemoria (studente,data,testo,docente,notificato) VALUES (?,?,?,?,?)',
                                     (nome, data_str, testo[:500], docente, 1 if silenzioso else 0))
                        if not silenzioso:
                            notifica_promemoria(nome, data_str, docente, testo)
            if silenzioso:
                _storico_fatto(conn, 'promemoria', nome)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SCHEDULER] Errore promemoria {nome}: {e}")

def _archivia_lezioni(conn, nome, registro):
    """Conserva le lezioni viste nel registro: Argo ne restituisce solo gli ultimi giorni,
    quindi l'orario si completa man mano che passano i giorni."""
    from orario_utils import _parse_data
    nuove = 0
    for r in registro:
        d = _parse_data(r.get('datGiorno'))
        ora = r.get('ora')
        materia = (r.get('materia') or '').strip()
        if not d or not materia or not isinstance(ora, int) or ora < 1:
            continue
        cur = conn.execute(
            'INSERT OR IGNORE INTO lezioni_registro (studente,data,ora,materia,docente) VALUES (?,?,?,?,?)',
            (nome, d.isoformat(), ora, materia, (r.get('docente') or '').strip()))
        nuove += cur.rowcount
    limite = (date.today() - timedelta(days=150)).isoformat()
    conn.execute('DELETE FROM lezioni_registro WHERE studente=? AND data<?', (nome, limite))
    return nuove

def sync_orario():
    """Aggiorna l'orario ricostruito dalle lezioni del registro (al massimo ogni ora per studente)"""
    from orario_utils import ricostruisci_orario
    for studente in get_studenti():
        nome = studente.get('nome', 'Studente')
        try:
            conn = get_db()
            ultimo = conn.execute(
                "SELECT MAX(aggiornato_il) AS t FROM orario WHERE studente=?", (nome,)
            ).fetchone()['t']
            n_giorni = conn.execute(
                'SELECT COUNT(DISTINCT data) AS n FROM lezioni_registro WHERE studente=?', (nome,)
            ).fetchone()['n']
            conn.close()
            # Archivio povero: riprova a ogni controllo (recupero dello storico); poi al massimo ogni ora
            attesa = timedelta(hours=1) if n_giorni >= 10 else timedelta(minutes=5)
            if ultimo:
                try:
                    if datetime.now() - datetime.strptime(ultimo, '%Y-%m-%d %H:%M:%S') < attesa:
                        continue
                except Exception:
                    pass
            # Archivio ancora povero: chiedo ad Argo anche i giorni passati; poi bastano gli ultimi giorni
            registro = fetch_registro(studente, giorni=60 if n_giorni < 10 else 7)
            date_viste = sorted({str(r.get('datGiorno'))[:10] for r in registro if r.get('datGiorno')})
            conn = get_db()
            nuove = _archivia_lezioni(conn, nome, registro)
            conn.commit()
            storico = conn.execute(
                'SELECT data, ora, materia, docente FROM lezioni_registro WHERE studente=?', (nome,)
            ).fetchall()
            conn.close()
            print(f"[SCHEDULER] Registro {nome}: {len(registro)} righe su {len(date_viste)} giorni "
                  f"({date_viste[0] if date_viste else '-'} → {date_viste[-1] if date_viste else '-'}), "
                  f"{nuove} lezioni nuove in archivio, {len(storico)} totali")
            slot = ricostruisci_orario([
                {'datGiorno': r['data'], 'ora': r['ora'], 'materia': r['materia'], 'docente': r['docente']}
                for r in storico])
            if not slot:
                print(f"[SCHEDULER] Orario {nome}: nessuna lezione utile, tengo quello salvato")
                continue
            conn = get_db()
            conn.execute('DELETE FROM orario WHERE studente=?', (nome,))
            conn.executemany(
                'INSERT INTO orario (studente,giorno,ora,materia,docente) VALUES (?,?,?,?,?)',
                [(nome, s['giorno'], s['ora'], s['materia'], s['docente']) for s in slot]
            )
            conn.commit()
            conn.close()
            giorni_ok = sorted({s['giorno'] for s in slot})
            print(f"[SCHEDULER] Orario {nome}: {len(slot)} ore su {len(giorni_ok)} giorni della settimana")
        except Exception as e:
            print(f"[SCHEDULER] Errore orario {nome}: {e}")

def sync_tutto():
    """Sync completo di tutto"""
    sync_compiti()
    sync_voti()
    sync_assenze()
    sync_note()
    sync_bacheca()
    sync_argomenti()
    sync_promemoria()
    sync_orario()
    for studente in get_studenti():
        _aggiorna_sensori(studente.get('nome', 'Studente'))

def _giorni_scuola(conn, nome):
    """Giorni della settimana (0=lun … 6=dom) con lezione, ricavati dall'orario ricostruito.
    Se l'orario non c'è ancora si assume lunedì-venerdì."""
    giorni = {r['giorno'] for r in conn.execute('SELECT DISTINCT giorno FROM orario WHERE studente=?', (nome,)).fetchall()}
    return giorni or {0, 1, 2, 3, 4}

def reminder_sera():
    print("[SCHEDULER] Reminder serale")
    domani_data = date.today() + timedelta(days=1)
    domani = domani_data.strftime('%Y-%m-%d')
    for studente in get_studenti():
        nome = studente.get('nome', 'Studente')
        try:
            conn = get_db()
            rows = conn.execute('SELECT materia, testo FROM compiti WHERE studente=? AND data=? ORDER BY materia', (nome, domani)).fetchall()
            domani_scuola = domani_data.weekday() in _giorni_scuola(conn, nome)
            orario_domani = [(r['ora'], r['materia']) for r in conn.execute(
                'SELECT ora, materia FROM orario WHERE studente=? AND giorno=? ORDER BY ora',
                (nome, domani_data.weekday())).fetchall()]
            conn.close()
            compiti_domani = {'materie':[r['materia'] for r in rows], 'compiti':[r['testo'] for r in rows]} if rows else None
            reminder_compiti_domani(nome, compiti_domani, domani_scuola=domani_scuola, orario_domani=orario_domani)
        except Exception as e:
            print(f"[SCHEDULER] Errore reminder {nome}: {e}")

def _taglia(s, n=400):
    s = str(s or '').strip()
    return s if len(s) <= n else s[:n - 1] + '…'


def _dettagli_sensori(conn, nome, oggi, domani):
    """Elenchi per il popup della card (attributo `elenco` dei sensori). Tenuti corti:
    Home Assistant sconsiglia attributi molto grandi."""
    def compiti(giorno):
        return [{'materia': r['materia'], 'testo': _taglia(r['testo'])} for r in conn.execute(
            'SELECT materia, testo FROM compiti WHERE studente=? AND data=? ORDER BY materia', (nome, giorno))]
    voti = [{'data': r['data'], 'materia': r['materia'], 'voto': r['voto'], 'descrizione': _taglia(r['descrizione'], 150)}
            for r in conn.execute(
                "SELECT data, materia, voto, descrizione FROM voti WHERE studente=? "
                "AND voto NOT IN ('0','0.0','0,0','N','') ORDER BY data DESC, id DESC LIMIT 15", (nome,))]
    per_materia = {}
    for r in conn.execute("SELECT materia, voto FROM voti WHERE studente=? AND voto NOT IN ('0','0.0','0,0','N','')", (nome,)):
        try:
            per_materia.setdefault(r['materia'], []).append(float(str(r['voto']).replace(',', '.')))
        except Exception:
            pass
    medie = sorted(({'materia': m, 'media': round(sum(v) / len(v), 1), 'n': len(v)} for m, v in per_materia.items()),
                   key=lambda x: x['materia'])
    assenze = [{'data': r['data'], 'tipo': r['tipo'], 'descrizione': _taglia(r['descrizione'], 150),
                'giustificata': bool(r['giustificata'])} for r in conn.execute(
                'SELECT data, tipo, descrizione, giustificata FROM assenze WHERE studente=? ORDER BY data DESC, id DESC LIMIT 20', (nome,))]
    bacheca = [{'data': r['data'], 'titolo': _taglia(r['titolo'], 120), 'mittente': r['mittente'] or '',
                'testo': _taglia(r['testo'], 500)} for r in conn.execute(
                'SELECT data, titolo, testo, mittente FROM bacheca WHERE studente=? ORDER BY data DESC, id DESC LIMIT 8', (nome,))]
    return {'compiti_oggi': compiti(oggi), 'compiti_domani': compiti(domani), 'voti': voti,
            'medie': medie, 'assenze': assenze, 'bacheca': bacheca}


def _aggiorna_sensori(nome):
    try:
        oggi = date.today().strftime('%Y-%m-%d')
        domani = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        conn = get_db()
        n_oggi   = conn.execute('SELECT COUNT(*) as n FROM compiti WHERE studente=? AND data=?', (nome, oggi)).fetchone()['n']
        n_domani = conn.execute('SELECT COUNT(*) as n FROM compiti WHERE studente=? AND data=?', (nome, domani)).fetchone()['n']
        n_assenze = conn.execute('SELECT COUNT(*) as n FROM assenze WHERE studente=?', (nome,)).fetchone()['n']
        n_bacheca = conn.execute('SELECT COUNT(*) as n FROM bacheca WHERE studente=? AND data>=?', (nome, (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'))).fetchone()['n']
        ultimo_voto = conn.execute("SELECT voto, materia FROM voti WHERE studente=? AND voto NOT IN ('0','0.0','0,0','N','') ORDER BY data DESC, id DESC LIMIT 1", (nome,)).fetchone()
        tutti_voti = conn.execute("SELECT voto FROM voti WHERE studente=? AND voto NOT IN ('0','0.0','0,0','N','')", (nome,)).fetchall()
        dettagli = _dettagli_sensori(conn, nome, oggi, domani)
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
            'media_voti': media,
            'dettagli': dettagli
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
