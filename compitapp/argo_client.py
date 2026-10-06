import os
import json
from argofamiglia import ArgoFamiglia

def get_studenti():
    raw = os.environ.get('STUDENTI', '[]')
    try:
        studenti = json.loads(raw)
        return [s for s in studenti if s.get('codice_scuola') and s.get('username')]
    except Exception as e:
        print(f"[ARGO] Errore parsing STUDENTI: {e}")
        return []

_sessions = {}

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
            print(f"[ARGO] ✅ Sessione creata per {nome}")
        return _sessions[nome]
    except Exception as e:
        print(f"[ARGO] ❌ Errore sessione {nome}: {e}")
        _sessions.pop(nome, None)
        return None

def _reset_session(nome):
    _sessions.pop(nome, None)

def fetch_dashboard(studente):
    """Recupera tutti i dati in una sola chiamata — con retry automatico"""
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

def fetch_voti(studente):
    """Estrae voti dalla dashboard"""
    dashboard = fetch_dashboard(studente)
    if not dashboard:
        return []
    try:
        voti = []
        dati = dashboard.get('data', {}).get('dati', [])
        for sezione in dati:
            # Voti giornalieri
            for v in sezione.get('votiGiornalieri', []):
                voti.append({
                    'data': v.get('datGiorno', ''),
                    'materia': v.get('desMateria', ''),
                    'voto': v.get('decVoto', '') or v.get('codVoto', ''),
                    'descrizione': v.get('desCommento', '')
                })
        return voti
    except Exception as e:
        print(f"[ARGO] Errore parsing voti: {e}")
        return []

def fetch_assenze(studente):
    """Estrae assenze dalla dashboard"""
    dashboard = fetch_dashboard(studente)
    if not dashboard:
        return []
    try:
        assenze = []
        dati = dashboard.get('data', {}).get('dati', [])
        for sezione in dati:
            for a in sezione.get('assenze', []):
                assenze.append({
                    'data': a.get('datAssenza', ''),
                    'tipo': a.get('codEvento', 'A'),  # A=assenza, R=ritardo, U=uscita
                    'descrizione': a.get('desAssenza', ''),
                    'giustificata': a.get('flgGiustificata', 'N') == 'S'
                })
        return assenze
    except Exception as e:
        print(f"[ARGO] Errore parsing assenze: {e}")
        return []

def fetch_note(studente):
    """Estrae note disciplinari dalla dashboard"""
    dashboard = fetch_dashboard(studente)
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

def fetch_bacheca(studente):
    """Estrae comunicazioni bacheca dalla dashboard"""
    dashboard = fetch_dashboard(studente)
    if not dashboard:
        return []
    try:
        bacheca = []
        dati = dashboard.get('data', {}).get('dati', [])
        for sezione in dati:
            for msg in sezione.get('bacheca', []):
                bacheca.append({
                    'data': msg.get('datPubblicazione', ''),
                    'titolo': msg.get('desOggetto', ''),
                    'testo': msg.get('desMessaggio', ''),
                    'mittente': msg.get('desMittente', ''),
                    'uid': msg.get('uid', '')
                })
            # Anche bacheca alunno
            for msg in sezione.get('bachecaAlunno', []):
                bacheca.append({
                    'data': msg.get('datPubblicazione', ''),
                    'titolo': msg.get('desOggetto', ''),
                    'testo': msg.get('desMessaggio', ''),
                    'mittente': msg.get('desMittente', ''),
                    'uid': msg.get('uid', '')
                })
        return bacheca
    except Exception as e:
        print(f"[ARGO] Errore parsing bacheca: {e}")
        return []

def fetch_argomenti(studente):
    """Estrae argomenti lezione dalla dashboard"""
    dashboard = fetch_dashboard(studente)
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
    Con `giorni` > 0 prova a recuperare anche i giorni passati; se non riesce usa la dashboard normale."""
    nome = studente.get('nome', 'default')
    if giorni:
        try:
            registro = _estrai_registro(_dashboard_dal(studente, giorni))
            if registro:
                return registro
            print(f"[ARGO] Registro {nome}: risposta vuota con storico di {giorni} giorni, uso la dashboard normale")
        except Exception as e:
            print(f"[ARGO] Registro {nome}: storico non disponibile ({e}), uso la dashboard normale")
            _reset_session(nome)
    dashboard = fetch_dashboard(studente)
    if not dashboard:
        return []
    try:
        return _estrai_registro(dashboard)
    except Exception as e:
        print(f"[ARGO] Errore lettura registro: {e}")
        return []

def fetch_orario(studente):
    """Orario settimanale ricostruito dalle lezioni del registro (Argo non lo espone direttamente)"""
    from orario_utils import ricostruisci_orario
    return ricostruisci_orario(fetch_registro(studente))

def fetch_promemoria(studente):
    """Estrae promemoria dalla dashboard"""
    dashboard = fetch_dashboard(studente)
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
