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
    """Recupera tutti i dati in una sola chiamata"""
    nome = studente.get('nome', 'default')
    try:
        session = get_session(studente)
        if not session:
            return None
        data = session.dashboard(useExactDatetime=False)
        return data
    except Exception as e:
        print(f"[ARGO] Errore dashboard {nome}: {e}")
        _reset_session(nome)
        return None

def fetch_compiti(studente):
    try:
        session = get_session(studente)
        if not session:
            return {}
        return session.getCompitiByDate() or {}
    except Exception as e:
        print(f"[ARGO] Errore compiti {studente.get('nome')}: {e}")
        _reset_session(studente.get('nome', ''))
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
