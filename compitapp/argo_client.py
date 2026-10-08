import os
import json
import time
import secrets
import requests
from argofamiglia import ArgoFamiglia
from argofamiglia.CONSTANTS import ENDPOINT

def get_studenti():
    raw = os.environ.get('STUDENTI', '[]')
    try:
        studenti = json.loads(raw)
        return [s for s in studenti if s.get('codice_scuola') and s.get('username')]
    except Exception as e:
        print(f"[ARGO] Errore parsing STUDENTI: {e}")
        return []

_sessions = {}


def _descrivi_profilo(p):
    """Testo breve per i registri (senza token)."""
    parti = []
    for k, v in p.items():
        if k == 'token' or v in (None, ''):
            continue
        if isinstance(v, (str, int)) and len(str(v)) < 60:
            parti.append(f"{k}={v}")
        elif isinstance(v, dict):
            for k2, v2 in v.items():
                if isinstance(v2, (str, int)) and len(str(v2)) < 60 and v2 not in (None, ''):
                    parti.append(f"{k}.{k2}={v2}")
    return ", ".join(parti[:12])


def _scegli_profilo(session, studente):
    """Un account Argo con più figli ha più "profili" (la schermata «Scelta profilo» dell'app DiDUP).
    La libreria usa sempre il primo: qui si sceglie quello indicato dal campo `alunno` (1, 2...)."""
    nome = studente.get('nome', 'default')
    try:
        indice = int(studente.get('alunno') or 0)
    except (TypeError, ValueError):
        indice = 0
    try:
        login_data = session._ArgoFamiglia__login_data
        r = requests.post(ENDPOINT + "login", timeout=30, headers={
            "Content-Type": "Application/json", "Accept": "Application/json",
            "Authorization": "Bearer " + login_data["access_token"]},
            json={"clientID": secrets.token_urlsafe(64), "lista-x-auth-token": "[]",
                  "x-auth-token-corrente": "null", "lista-opzioni-notifiche": "{}"})
        profili = r.json().get('data') or []
    except Exception as e:
        print(f"[ARGO] {nome}: elenco profili non disponibile ({e})")
        return
    if len(profili) > 1:
        print(f"[ARGO] {nome}: l'account Argo contiene {len(profili)} profili"
              + ("" if indice else " — compila il campo 'alunno' (1, 2...) per ogni figlio, altrimenti usa sempre il primo"))
        for i, p in enumerate(profili, 1):
            print(f"[ARGO]   profilo {i}: {_descrivi_profilo(p)}")
    if not indice or not profili:
        return
    if indice > len(profili):
        print(f"[ARGO] {nome}: alunno={indice} ma l'account ha {len(profili)} profili, uso l'ultimo")
        indice = len(profili)
    token = profili[indice - 1].get('token')
    if token:
        session._ArgoFamiglia__token = token
        session._ArgoFamiglia__headers["x-auth-token"] = token
        print(f"[ARGO] {nome}: uso il profilo {indice} di {len(profili)}")

def get_session(studente):
    nome = studente.get('nome', 'default')
    global _sessions
    try:
        if nome not in _sessions:
            _sessions[nome] = ArgoFamiglia(
                studente['codice_scuola'],
                studente['username'],
                studente['password']
            )
            _scegli_profilo(_sessions[nome], studente)
            print(f"[ARGO] ✅ Sessione creata per {nome}")
        return _sessions[nome]
    except Exception as e:
        print(f"[ARGO] ❌ Errore sessione {nome}: {e}")
        _sessions.pop(nome, None)
        return None

def _reset_session(nome):
    _sessions.pop(nome, None)

_cache_dashboard = {}
CACHE_SECONDI = 90
_sezioni_loggate = set()


def _filtra_alunno(studente, data):
    """Un account Argo con più figli restituisce una sezione per alunno in data.dati.
    Con il campo `alunno` (1 = primo, 2 = secondo...) teniamo solo quella dello studente."""
    try:
        dati = data.get('data', {}).get('dati', [])
    except AttributeError:
        return data
    nome = studente.get('nome', 'default')
    if len(dati) <= 1:
        return data
    if nome not in _sezioni_loggate:
        _sezioni_loggate.add(nome)
        print(f"[ARGO] {nome}: l'account Argo contiene {len(dati)} alunni"
              + ("" if studente.get('alunno') else " — compila il campo 'alunno' (1, 2...) per ogni figlio, altrimenti i dati si mescolano"))
    try:
        indice = int(studente.get('alunno') or 0)
    except (TypeError, ValueError):
        indice = 0
    if indice and dati:
        if indice > len(dati):
            print(f"[ARGO] {nome}: alunno={indice} ma l'account ne ha {len(dati)}, uso l'ultimo")
            indice = len(dati)
        copia = dict(data)
        copia['data'] = dict(data['data'])
        copia['data']['dati'] = [dati[indice - 1]]
        return copia
    return data

def fetch_dashboard(studente, giorni=0):
    """Dashboard di Argo. Con `giorni` > 0 chiede le novità dalle ultime `giorni` giornate
    (la richiesta standard restituisce soltanto quelle di oggi); se non riesce usa la standard.
    Il risultato è riusato per qualche secondo: un ciclo di sincronizzazione fa molte letture."""
    nome = studente.get('nome', 'default')
    chiave = (nome, giorni)
    voce = _cache_dashboard.get(chiave)
    if voce and time.time() - voce[0] < CACHE_SECONDI:
        return voce[1]
    data = None
    if giorni:
        try:
            data = _dashboard_dal(studente, giorni)
            if not (isinstance(data, dict) and data.get('data')):
                print(f"[ARGO] Dashboard {nome}: risposta vuota con storico di {giorni} giorni, uso quella standard")
                data = None
        except Exception as e:
            print(f"[ARGO] Dashboard {nome}: storico non disponibile ({e}), uso quella standard")
            _reset_session(nome)
            data = None
    if data is None:
        data = _dashboard_standard(studente)
    if data is not None:
        data = _filtra_alunno(studente, data)
        _cache_dashboard[chiave] = (time.time(), data)
    return data

def _dashboard_standard(studente):
    """Dashboard standard (solo le novità di oggi) — con retry automatico"""
    nome = studente.get('nome', 'default')
    for tentativo in range(3):
        try:
            session = get_session(studente)
            if not session:
                return None
            data = session.dashboard(useExactDatetime=False)
            if data is None and tentativo < 2:
                print(f"[ARGO] Risposta vuota dashboard {nome} — retry {tentativo+1}/3")
                _reset_session(nome)
                continue
            return data
        except ValueError as e:
            print(f"[ARGO] Sessione scaduta {nome} — rinnovo dashboard (tentativo {tentativo+1}/3)")
            _reset_session(nome)
            if tentativo == 2:
                print(f"[ARGO] ❌ Impossibile recuperare dashboard {nome} dopo 3 tentativi")
                return None
        except Exception as e:
            print(f"[ARGO] Errore dashboard {nome}: {e}")
            _reset_session(nome)
            return None
    return None

def fetch_compiti(studente):
    nome = studente.get('nome', '')
    for tentativo in range(3):  # Fino a 3 tentativi
        try:
            session = get_session(studente)
            if not session:
                return {}
            risultato = session.getCompitiByDate()
            if risultato is None and tentativo < 2:
                print(f"[ARGO] Risposta vuota compiti {nome} — retry {tentativo+1}/3")
                _reset_session(nome)
                continue
            return risultato or {}
        except ValueError as e:
            # Risposta JSON vuota — sessione scaduta
            print(f"[ARGO] Sessione scaduta {nome} — rinnovo (tentativo {tentativo+1}/3)")
            _reset_session(nome)
            if tentativo == 2:
                print(f"[ARGO] ❌ Impossibile recuperare compiti {nome} dopo 3 tentativi")
                return {}
        except Exception as e:
            print(f"[ARGO] Errore compiti {nome}: {e}")
            _reset_session(nome)
            return {}
    return {}

def _pick(d, *chiavi, default=''):
    """Primo campo valorizzato tra i nomi candidati (Argo cambia nomi tra versioni)."""
    for k in chiavi:
        v = d.get(k)
        if v not in (None, ''):
            return v
    return default


def _voto_valido(valore):
    """True se e' un vero voto. Scarta le annotazioni senza voto (valore 0 / vuoto)."""
    if valore in (None, ''):
        return False
    t = str(valore).strip().replace(',', '.')
    try:
        return float(t) > 0
    except ValueError:
        return t.upper() not in ('N', '-', '--')   # voti a giudizio (es. "Ottimo")


def fetch_voti(studente, giorni=0):
    """Estrae voti dalla dashboard (lista 'voti', o 'votiGiornalieri' nelle versioni vecchie)"""
    dashboard = fetch_dashboard(studente, giorni)
    if not dashboard:
        return []
    try:
        voti = []
        dati = dashboard.get('data', {}).get('dati', [])
        for sezione in dati:
            for v in list(sezione.get('voti', []) or []) + list(sezione.get('votiGiornalieri', []) or []):
                valore = _pick(v, 'valore', 'decValore', 'decVoto', 'codVoto')
                if not _voto_valido(valore):
                    continue
                materia = _pick(v, 'desMateria', 'materia', 'descrizioneMateria')
                if isinstance(materia, dict):
                    materia = _pick(materia, 'descrizione', 'desMateria', 'nome')
                voti.append({
                    'data': _pick(v, 'datGiorno', 'data', 'dataVoto'),
                    'materia': materia or 'Materia',
                    'voto': str(valore),
                    'descrizione': _pick(v, 'desCommento', 'commento', 'descrizione', 'desProva')
                })
        return voti
    except Exception as e:
        print(f"[ARGO] Errore parsing voti: {e}")
        return []

def _bool_arg(v):
    return v is True or str(v).upper() in ('S', 'TRUE', '1')

def fetch_assenze(studente, giorni=0):
    """Estrae assenze/ritardi/uscite (lista 'appello', o 'assenze' nelle versioni vecchie)"""
    dashboard = fetch_dashboard(studente, giorni)
    if not dashboard:
        return []
    try:
        assenze = []
        dati = dashboard.get('data', {}).get('dati', [])
        for sezione in dati:
            for a in list(sezione.get('appello', []) or []) + list(sezione.get('assenze', []) or []):
                assenze.append({
                    'data': _pick(a, 'data', 'datAssenza'),
                    'tipo': _pick(a, 'codEvento', default='A'),  # A=assenza, R=ritardo, U=uscita
                    'descrizione': _pick(a, 'descrizione', 'desAssenza'),
                    'giustificata': _bool_arg(_pick(a, 'giustificata', 'flgGiustificata', default='N'))
                })
        return assenze
    except Exception as e:
        print(f"[ARGO] Errore parsing assenze: {e}")
        return []

def fetch_note(studente, giorni=0):
    """Estrae note disciplinari dalla dashboard"""
    dashboard = fetch_dashboard(studente, giorni)
    if not dashboard:
        return []
    try:
        note = []
        dati = dashboard.get('data', {}).get('dati', [])
        for sezione in dati:
            for n in sezione.get('noteDisciplinari', []):
                note.append({
                    'data': n.get('datNota', ''),
                    'docente': n.get('docente', ''),
                    'testo': n.get('desNota', '')
                })
        return note
    except Exception as e:
        print(f"[ARGO] Errore parsing note: {e}")
        return []

def _msg_bacheca(msg):
    testo = _pick(msg, 'messaggio', 'desMessaggio')
    titolo = _pick(msg, 'desOggetto', 'titolo', 'oggetto', 'categoria')
    if not titolo:
        titolo = (str(testo).strip().splitlines() or [''])[0][:80] or 'Comunicazione'
    return {
        'data': _pick(msg, 'data', 'datPubblicazione'),
        'titolo': titolo,
        'testo': testo,
        'mittente': _pick(msg, 'autore', 'desMittente'),
        'uid': str(_pick(msg, 'pk', 'uid'))
    }

def fetch_bacheca(studente, giorni=0):
    """Estrae comunicazioni bacheca dalla dashboard"""
    dashboard = fetch_dashboard(studente, giorni)
    if not dashboard:
        return []
    try:
        bacheca = []
        dati = dashboard.get('data', {}).get('dati', [])
        for sezione in dati:
            for chiave in ('bacheca', 'bachecaAlunno'):
                for msg in sezione.get(chiave, []) or []:
                    bacheca.append(_msg_bacheca(msg))
        return bacheca
    except Exception as e:
        print(f"[ARGO] Errore parsing bacheca: {e}")
        return []

def fetch_argomenti(studente, giorni=0):
    """Estrae argomenti lezione dalla dashboard"""
    dashboard = fetch_dashboard(studente, giorni)
    if not dashboard:
        return []
    try:
        argomenti = []
        dati = dashboard.get('data', {}).get('dati', [])
        for sezione in dati:
            materia = sezione.get('materia', '')
            for arg in sezione.get('argomentiLezione', []):
                argomenti.append({
                    'data': arg.get('datGiorno', ''),
                    'materia': materia,
                    'argomento': arg.get('desArgomento', ''),
                    'attivita': arg.get('desAttivita', '')
                })
        return argomenti
    except Exception as e:
        print(f"[ARGO] Errore parsing argomenti: {e}")
        return []

def _estrai_registro(dashboard):
    registro = []
    for sezione in (dashboard or {}).get('data', {}).get('dati', []):
        registro.extend(sezione.get('registro', []))
    return registro

def _dashboard_dal(studente, giorni):
    """Dashboard con "novità dal" spostato indietro di `giorni` giorni.
    La libreria chiede solo le novità di oggi (00:00), quindi il registro contiene
    soltanto le lezioni di oggi: con una data più vecchia Argo restituisce anche i giorni precedenti."""
    import datetime
    import requests
    from argofamiglia.CONSTANTS import ENDPOINT, DASHBOARD_OPTIONS
    session = get_session(studente)
    if not session:
        return None
    dal = datetime.datetime.now() - datetime.timedelta(days=giorni)
    risposta = requests.post(
        ENDPOINT + "dashboard/dashboard",
        headers=session._ArgoFamiglia__headers,
        json={"dataultimoaggiornamento": dal.strftime("%Y-%m-%d 00:00:00"),
              "opzioni": json.dumps(DASHBOARD_OPTIONS)},
        timeout=60)
    return risposta.json()

def fetch_registro(studente, giorni=0):
    """Lezioni del registro (lista di dict con datGiorno, ora, materia, docente).
    Con `giorni` > 0 prova a recuperare anche i giorni passati."""
    nome = studente.get('nome', 'default')
    try:
        registro = _estrai_registro(fetch_dashboard(studente, giorni))
        if registro and giorni:
            giorni_visti = len({str(r.get('datGiorno'))[:10] for r in registro})
            print(f"[ARGO] Registro {nome}: richiesta con storico di {giorni} giorni → {len(registro)} righe su {giorni_visti} giorni")
        if not registro and giorni:
            registro = _estrai_registro(fetch_dashboard(studente))
        return registro
    except Exception as e:
        print(f"[ARGO] Errore lettura registro: {e}")
        return []

def fetch_orario(studente):
    """Orario settimanale ricostruito dalle lezioni del registro (Argo non lo espone direttamente)"""
    from orario_utils import ricostruisci_orario
    return ricostruisci_orario(fetch_registro(studente))

def fetch_promemoria(studente, giorni=0):
    """Estrae promemoria dalla dashboard"""
    dashboard = fetch_dashboard(studente, giorni)
    if not dashboard:
        return []
    try:
        promemoria = []
        dati = dashboard.get('data', {}).get('dati', [])
        for sezione in dati:
            for p in sezione.get('promemoria', []):
                promemoria.append({
                    'data': p.get('datGiorno', ''),
                    'testo': p.get('desAnnotazioni', ''),
                    'docente': p.get('docente', '')
                })
        return promemoria
    except Exception as e:
        print(f"[ARGO] Errore parsing promemoria: {e}")
        return []
