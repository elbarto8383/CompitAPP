"""
Connettore per registro elettronico Argo (DiDUP / ScuolaNext).
Incapsula le chiamate alla libreria argofamiglia e la gestione delle sessioni multi-profilo.
"""

import datetime
import json
import secrets
import time
from typing import Any, Dict, List, Optional

import requests

try:
    from argofamiglia import ArgoFamiglia
    from argofamiglia.CONSTANTS import DASHBOARD_OPTIONS, ENDPOINT
except ImportError:
    ArgoFamiglia = Any  # type: ignore
    DASHBOARD_OPTIONS = {}
    ENDPOINT = "https://www.portaleargo.it/famiglia/api/rest/"

from .base import BaseConnector

# Cache condivisa delle sessioni e delle risposte dashboard
_sessions: Dict[str, ArgoFamiglia] = {}
_cache_dashboard: Dict[tuple, tuple] = {}
CACHE_SECONDI = 90
_sezioni_loggate = set()
_voti_campi_loggati = set()


def _descrivi_profilo(p: Dict[str, Any]) -> str:
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


def _scegli_profilo(session: ArgoFamiglia, studente: Dict[str, Any]) -> None:
    """Un account Argo con piu' figli ha piu' "profili" (la schermata «Scelta profilo» dell'app DiDUP).
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
    _controlla_cambio_profilo(nome, indice if len(profili) > 1 else 0)
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


def _controlla_cambio_profilo(nome: str, indice: int) -> None:
    """Se il profilo scelto (campo `alunno`) e' cambiato dall'ultima volta, i dati salvati
    appartengono a un altro alunno: si cancellano e lo storico viene ricaricato."""
    try:
        from models import get_db, svuota_studente
        conn = get_db()
        r = conn.execute('SELECT valore FROM meta WHERE chiave=?', (f"profilo:{nome}",)).fetchone()
        precedente = r['valore'] if r else None
        attuale = str(indice or 0)
        # Pulizia una tantum (2.0.5): chi ha usato versioni precedenti con un alunno 2, 3... puo' avere
        # nel database compiti, voti e lezioni del PRIMO figlio mescolati a quelli giusti, e nessuna
        # versione se ne accorgeva (il profilo risultava gia' "registrato" senza che i dati fossero puliti).
        chiave_pulizia = f"pulizia_profilo:{nome}"
        pulizia_fatta = conn.execute('SELECT 1 FROM meta WHERE chiave=?', (chiave_pulizia,)).fetchone() is not None
        pulizia_necessaria = (not pulizia_fatta) and attuale not in ('0', '1')
        if (precedente is not None and precedente != attuale) or pulizia_necessaria:
            svuota_studente(conn, nome)
            motivo = "cambio di profilo" if (precedente is not None and precedente != attuale) else "pulizia una tantum dei dati"
            print(f"[ARGO] {nome}: {motivo} (profilo {precedente or '?'} → {attuale}): "
                  "cancello i dati vecchi e ricarico l'anno scolastico")
        conn.execute("INSERT OR REPLACE INTO meta (chiave, valore) VALUES (?, '1')", (chiave_pulizia,))
        conn.execute("INSERT OR REPLACE INTO meta (chiave, valore) VALUES (?, ?)", (f"profilo:{nome}", attuale))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[ARGO] {nome}: controllo cambio profilo non riuscito ({e})")


def _pick(d: Dict[str, Any], *chiavi: str, default: Any = '') -> Any:
    """Primo campo valorizzato tra i nomi candidati (Argo cambia nomi tra versioni)."""
    for k in chiavi:
        v = d.get(k)
        if v not in (None, ''):
            return v
    return default


def _voto_valido(valore: Any) -> bool:
    """True se e' un vero voto. Scarta le annotazioni senza voto (valore 0 / vuoto)."""
    if valore in (None, ''):
        return False
    t = str(valore).strip().replace(',', '.')
    try:
        return float(t) > 0
    except ValueError:
        return t.upper() not in ('N', '-', '--')   # voti a giudizio (es. "Ottimo")


def _bool_arg(v: Any) -> bool:
    return v is True or str(v).upper() in ('S', 'TRUE', '1')


def _msg_bacheca(msg: Dict[str, Any]) -> Dict[str, Any]:
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


def _estrai_registro(dashboard: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    registro = []
    for sezione in (dashboard or {}).get('data', {}).get('dati', []):
        registro.extend(sezione.get('registro', []))
    return registro


def _log_campi_voto(nome: str, sezione: Dict[str, Any]) -> None:
    """Una volta per studente stampa i campi di un voto come arrivano da Argo (aiuta a capire
    come Argo segna i voti «non fa media»). Niente credenziali o token."""
    global _voti_campi_loggati
    if nome in _voti_campi_loggati:
        return
    voti = list(sezione.get('voti', []) or [])
    if not voti:
        return
    _voti_campi_loggati.add(nome)
    for v in voti[:2]:
        parti = [f"{k}={v[k]}" for k in sorted(v) if not isinstance(v[k], (dict, list)) and len(str(v[k])) < 80]
        print(f"[ARGO] Campi di un voto ({nome}): " + ", ".join(parti))


class ArgoConnector(BaseConnector):
    """Connettore per registro elettronico Argo (DiDUP)."""

    def get_session(self) -> Optional[ArgoFamiglia]:
        """Inizializza o restituisce la sessione ArgoFamiglia per lo studente."""
        global _sessions
        try:
            if self.nome not in _sessions:
                _sessions[self.nome] = ArgoFamiglia(
                    self.studente['codice_scuola'],
                    self.studente['username'],
                    self.studente['password']
                )
                _scegli_profilo(_sessions[self.nome], self.studente)
                print(f"[ARGO] Sessione creata per {self.nome}")
            return _sessions[self.nome]
        except Exception as e:
            print(f"[ARGO] Errore sessione {self.nome}: {e}")
            _sessions.pop(self.nome, None)
            return None

    def reset_session(self) -> None:
        _sessions.pop(self.nome, None)

    def _filtra_alunno(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Un account Argo con piu' figli restituisce una sezione per alunno in data.dati.
        Con il campo `alunno` (1 = primo, 2 = secondo...) teniamo solo quella dello studente."""
        try:
            dati = data.get('data', {}).get('dati', [])
        except AttributeError:
            return data
        if len(dati) <= 1:
            return data
        if self.nome not in _sezioni_loggate:
            _sezioni_loggate.add(self.nome)
            print(f"[ARGO] {self.nome}: l'account Argo contiene {len(dati)} alunni"
                  + ("" if self.studente.get('alunno') else " — compila il campo 'alunno' (1, 2...) per ogni figlio, altrimenti i dati si mescolano"))
        try:
            indice = int(self.studente.get('alunno') or 0)
        except (TypeError, ValueError):
            indice = 0
        if indice and dati:
            if indice > len(dati):
                print(f"[ARGO] {self.nome}: alunno={indice} ma l'account ne ha {len(dati)}, uso l'ultimo")
                indice = len(dati)
            copia = dict(data)
            copia['data'] = dict(data['data'])
            copia['data']['dati'] = [dati[indice - 1]]
            return copia
        return data

    def _dashboard_dal(self, giorni: int) -> Optional[Dict[str, Any]]:
        """Dashboard con "novita' dal" spostato indietro di `giorni` giorni."""
        session = self.get_session()
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

    def _dashboard_standard(self) -> Optional[Dict[str, Any]]:
        """Dashboard standard (solo le novita' di oggi) — con retry automatico"""
        for tentativo in range(3):
            try:
                session = self.get_session()
                if not session:
                    return None
                data = session.dashboard(useExactDatetime=False)
                if data is None and tentativo < 2:
                    print(f"[ARGO] Risposta vuota dashboard {self.nome} — retry {tentativo+1}/3")
                    self.reset_session()
                    continue
                return data
            except ValueError:
                print(f"[ARGO] Sessione scaduta {self.nome} — rinnovo dashboard (tentativo {tentativo+1}/3)")
                self.reset_session()
                if tentativo == 2:
                    print(f"[ARGO] Impossibile recuperare dashboard {self.nome} dopo 3 tentativi")
                    return None
            except Exception as e:
                print(f"[ARGO] Errore dashboard {self.nome}: {e}")
                self.reset_session()
                return None
        return None

    def fetch_dashboard(self, giorni: int = 0) -> Optional[Dict[str, Any]]:
        chiave = (self.nome, giorni)
        voce = _cache_dashboard.get(chiave)
        if voce and time.time() - voce[0] < CACHE_SECONDI:
            return voce[1]
        data = None
        if giorni:
            try:
                data = self._dashboard_dal(giorni)
                if not (isinstance(data, dict) and data.get('data')):
                    print(f"[ARGO] Dashboard {self.nome}: risposta vuota con storico di {giorni} giorni, uso quella standard")
                    data = None
            except Exception as e:
                print(f"[ARGO] Dashboard {self.nome}: storico non disponibile ({e}), uso quella standard")
                self.reset_session()
                data = None
        if data is None:
            data = self._dashboard_standard()
        if data is not None:
            data = self._filtra_alunno(data)
            _cache_dashboard[chiave] = (time.time(), data)
        return data

    def fetch_compiti(self) -> Dict[str, Any]:
        for tentativo in range(3):
            try:
                session = self.get_session()
                if not session:
                    return {}
                risultato = session.getCompitiByDate()
                if risultato is None and tentativo < 2:
                    print(f"[ARGO] Risposta vuota compiti {self.nome} — retry {tentativo+1}/3")
                    self.reset_session()
                    continue
                return risultato or {}
            except ValueError:
                print(f"[ARGO] Sessione scaduta {self.nome} — rinnovo (tentativo {tentativo+1}/3)")
                self.reset_session()
                if tentativo == 2:
                    print(f"[ARGO] Impossibile recuperare compiti {self.nome} dopo 3 tentativi")
                    return {}
            except Exception as e:
                print(f"[ARGO] Errore compiti {self.nome}: {e}")
                self.reset_session()
                return {}
        return {}

    def fetch_voti(self, giorni: int = 0) -> List[Dict[str, Any]]:
        dashboard = self.fetch_dashboard(giorni)
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

    def fetch_assenze(self, giorni: int = 0) -> List[Dict[str, Any]]:
        dashboard = self.fetch_dashboard(giorni)
        if not dashboard:
            return []
        try:
            assenze = []
            dati = dashboard.get('data', {}).get('dati', [])
            for sezione in dati:
                for a in list(sezione.get('appello', []) or []) + list(sezione.get('assenze', []) or []):
                    assenze.append({
                        'data': _pick(a, 'data', 'datAssenza'),
                        'tipo': _pick(a, 'codEvento', default='A'),
                        'descrizione': _pick(a, 'descrizione', 'desAssenza'),
                        'giustificata': _bool_arg(_pick(a, 'giustificata', 'flgGiustificata', default='N'))
                    })
            return assenze
        except Exception as e:
            print(f"[ARGO] Errore parsing assenze: {e}")
            return []

    def fetch_note(self, giorni: int = 0) -> List[Dict[str, Any]]:
        dashboard = self.fetch_dashboard(giorni)
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

    def fetch_bacheca(self, giorni: int = 0) -> List[Dict[str, Any]]:
        dashboard = self.fetch_dashboard(giorni)
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

    def fetch_argomenti(self, giorni: int = 0) -> List[Dict[str, Any]]:
        dashboard = self.fetch_dashboard(giorni)
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

    def fetch_registro(self, giorni: int = 0) -> List[Dict[str, Any]]:
        try:
            registro = _estrai_registro(self.fetch_dashboard(giorni))
            if registro and giorni:
                giorni_visti = len({str(r.get('datGiorno'))[:10] for r in registro})
                print(f"[ARGO] Registro {self.nome}: richiesta con storico di {giorni} giorni → {len(registro)} righe su {giorni_visti} giorni")
            if not registro and giorni:
                registro = _estrai_registro(self.fetch_dashboard())
            return registro
        except Exception as e:
            print(f"[ARGO] Errore lettura registro: {e}")
            return []

    def fetch_orario(self) -> Dict[str, Any]:
        from orario_utils import ricostruisci_orario
        return ricostruisci_orario(self.fetch_registro())

    def fetch_promemoria(self, giorni: int = 0) -> List[Dict[str, Any]]:
        dashboard = self.fetch_dashboard(giorni)
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

    def fetch_medie(self, giorni: int = 0) -> Optional[Dict[str, Any]]:
        dashboard = self.fetch_dashboard(giorni)
        if not dashboard:
            return None
        try:
            for sezione in dashboard.get('data', {}).get('dati', []):
                _log_campi_voto(self.nome, sezione)
                nomi = {}
                for m in sezione.get('listaMaterie') or []:
                    if isinstance(m, dict):
                        nomi[str(m.get('pk'))] = m.get('materia') or m.get('desMateria') or m.get('descrizione')
                materie = {}
                mm = sezione.get('mediaMaterie') or {}
                righe = mm.items() if isinstance(mm, dict) else ((str(x.get('pk')), x) for x in mm if isinstance(x, dict))
                for pk, m in righe:
                    if isinstance(m, dict) and m.get('mediaMateria') not in (None, '', 0, '0'):
                        materie[nomi.get(str(pk)) or str(pk)] = m.get('mediaMateria')
                generale = sezione.get('mediaGenerale')
                print(f"[ARGO] Medie Argo {self.nome}: generale={generale}, materie={materie}")
                if generale in (None, '') and not materie:
                    return None
                return {'generale': generale, 'materie': materie}
        except Exception as e:
            print(f"[ARGO] Errore lettura medie {self.nome}: {e}")
        return None
