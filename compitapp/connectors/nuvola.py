"""
Connettore per registro elettronico Nuvola (Madisoft S.p.A.) per CompitAPP.
Eredita da BaseConnector e normalizza i dati nei formati previsti dal database e dallo scheduler.
"""

from datetime import date, datetime, timedelta
import os
import tempfile
from typing import Any, Dict, List, Optional

from nuvola_api import NuvolaClient, NuvolaError
from .base import BaseConnector

_nuvola_clients: Dict[tuple, NuvolaClient] = {}


class NuvolaConnector(BaseConnector):
    """Connettore per registro elettronico Nuvola (Madisoft S.p.A.)."""

    def get_client(self) -> Optional[NuvolaClient]:
        """Inizializza o recupera l'istanza autenticata di NuvolaClient per lo studente."""
        global _nuvola_clients
        username = str(self.studente.get("username") or "").strip()
        cache_key = (self.nome, username)
        if cache_key not in _nuvola_clients:
            data_dir = os.environ.get("DATA_DIR")
            if not data_dir:
                data_dir = "/data" if os.path.isdir("/data") and os.access("/data", os.W_OK) else tempfile.gettempdir()
            safe_user = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in username)
            safe_nome = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in self.nome)
            session_file = os.path.join(data_dir, f"nuvola_session_{safe_user}_{safe_nome}.json")
            client = NuvolaClient(
                username=username,
                password=self.studente.get("password"),
                session_file=session_file,
                auto_save_session=True,
            )
            try:
                if not client.is_authenticated():
                    client.login()
                _nuvola_clients[cache_key] = client
                print(f"[NUVOLA] Sessione inizializzata per {self.nome}")
            except NuvolaError as e:
                print(f"[NUVOLA] Errore autenticazione {self.nome}: {e}")
                return None
            except Exception as e:
                print(f"[NUVOLA] Errore imprevisto inizializzazione {self.nome}: {e}")
                return None
        return _nuvola_clients[cache_key]

    def reset_client(self) -> None:
        username = str(self.studente.get("username") or "").strip()
        _nuvola_clients.pop((self.nome, username), None)

    def _get_alunno_id(self) -> Optional[int]:
        """Determina l'ID numerico dell'alunno Nuvola (da config o selezionando il profilo configurato)."""
        if self.studente.get("alunno_id"):
            try:
                return int(self.studente["alunno_id"])
            except (ValueError, TypeError):
                pass

        client = self.get_client()
        if not client:
            return None

        try:
            alunni = client.get_alunni()
            if not alunni:
                return None

            try:
                indice = int(self.studente.get("alunno") or 1)
            except (ValueError, TypeError):
                indice = 1

            if indice < 1:
                indice = 1
            if indice > len(alunni):
                indice = len(alunni)

            alunno_selezionato = alunni[indice - 1]
            return alunno_selezionato.id
        except Exception as e:
            print(f"[NUVOLA] Errore determinazione alunno ID per {self.nome}: {e}")
            return None

    def fetch_dashboard(self, giorni: int = 0) -> Optional[Dict[str, Any]]:
        return {"connettore": "nuvola", "studente": self.nome}

    def fetch_compiti(self) -> Dict[str, Any]:
        client = self.get_client()
        if not client:
            return {}
        alunno_id = self._get_alunno_id()
        if not alunno_id:
            return {}

        risultato: Dict[str, Dict[str, List[str]]] = {}
        oggi = date.today()
        for delta in range(15):
            giorno = oggi + timedelta(days=delta)
            data_param = giorno.strftime("%d-%m-%Y")
            data_db = giorno.strftime("%Y-%m-%d")
            try:
                compiti_giorno = client.get_compiti(alunno_id, data_param)
                if compiti_giorno:
                    materie = []
                    compiti_testi = []
                    for c in compiti_giorno:
                        mat = c.materia or "Materia"
                        desc = c.descrizione or c.titolo or ""
                        testo = f"{c.docente}: {desc}".strip() if c.docente else desc
                        materie.append(mat)
                        compiti_testi.append(testo)
                    risultato[data_db] = {
                        "materie": materie,
                        "compiti": compiti_testi,
                    }
            except Exception:
                continue
        return risultato

    def fetch_voti(self, giorni: int = 0) -> List[Dict[str, Any]]:
        client = self.get_client()
        if not client:
            return []
        alunno_id = self._get_alunno_id()
        if not alunno_id:
            return []

        try:
            voti_raw = client.get_tutti_voti(alunno_id)
            risultato = []
            for v in voti_raw:
                data_val = str(v.data)[:10]
                risultato.append({
                    "data": data_val,
                    "materia": v.nome_materia or "Materia",
                    "voto": str(v.valutazione),
                    "descrizione": v.descrizione or v.tipologia or "",
                })
            return risultato
        except Exception as e:
            print(f"[NUVOLA] Errore recupero voti {self.nome}: {e}")
            return []

    def fetch_assenze(self, giorni: int = 0) -> List[Dict[str, Any]]:
        client = self.get_client()
        if not client:
            return []
        alunno_id = self._get_alunno_id()
        if not alunno_id:
            return []

        mappa_tipo = {
            "ASSENZA": "A",
            "RITARDO": "R",
            "USCITA_ANTICIPATA": "U",
        }

        try:
            assenze_raw = client.get_assenze(alunno_id)
            risultato = []
            for a in assenze_raw:
                data_val = str(a.data)[:10]
                tipo_sigla = mappa_tipo.get(str(a.tipo).upper(), "A")
                desc = a.turno or ""
                if a.ora:
                    desc = f"{desc} (ore {a.ora})".strip()
                risultato.append({
                    "data": data_val,
                    "tipo": tipo_sigla,
                    "descrizione": desc,
                    "giustificata": bool(a.giustificata),
                })
            return risultato
        except Exception as e:
            print(f"[NUVOLA] Errore recupero assenze {self.nome}: {e}")
            return []

    def fetch_note(self, giorni: int = 0) -> List[Dict[str, Any]]:
        client = self.get_client()
        if not client:
            return []
        alunno_id = self._get_alunno_id()
        if not alunno_id:
            return []

        try:
            note_raw = client.get_note(alunno_id)
            return [
                {
                    "data": str(n.data)[:10],
                    "docente": n.docente or "",
                    "testo": n.descrizione or "",
                }
                for n in note_raw
            ]
        except Exception as e:
            print(f"[NUVOLA] Errore recupero note {self.nome}: {e}")
            return []

    def fetch_bacheca(self, giorni: int = 0) -> List[Dict[str, Any]]:
        client = self.get_client()
        if not client:
            return []
        alunno_id = self._get_alunno_id()
        if not alunno_id:
            return []

        try:
            eventi = client.get_eventi_classe(alunno_id)
            risultato = []
            for ev in eventi:
                risultato.append({
                    "data": str(ev.data_inizio)[:10],
                    "titolo": ev.nome or ev.tipo or "Comunicazione",
                    "testo": ev.descrizione or "",
                    "mittente": ev.docente or "Scuola",
                    "uid": f"nuvola_evento_{ev.id}",
                })
            return risultato
        except Exception as e:
            print(f"[NUVOLA] Errore recupero bacheca {self.nome}: {e}")
            return []

    def fetch_argomenti(self, giorni: int = 0) -> List[Dict[str, Any]]:
        client = self.get_client()
        if not client:
            return []
        alunno_id = self._get_alunno_id()
        if not alunno_id:
            return []

        risultato = []
        finestra = max(7, giorni) if giorni > 0 else 7
        oggi = date.today()
        for delta in range(finestra):
            giorno = oggi - timedelta(days=delta)
            data_param = giorno.strftime("%d-%m-%Y")
            try:
                ore = client.get_argomenti_lezione(alunno_id, data_param)
                for o in ore:
                    for arg in o.argomenti:
                        risultato.append({
                            "data": str(o.giorno)[:10],
                            "materia": arg.materia or "Materia",
                            "argomento": arg.nome_argomento or "",
                            "attivita": arg.tipo or "",
                        })
            except Exception:
                continue
        return risultato

    def fetch_promemoria(self, giorni: int = 0) -> List[Dict[str, Any]]:
        client = self.get_client()
        if not client:
            return []
        alunno_id = self._get_alunno_id()
        if not alunno_id:
            return []

        try:
            eventi = client.get_eventi_classe(alunno_id)
            return [
                {
                    "data": str(ev.data_inizio)[:10],
                    "testo": f"{ev.nome}: {ev.descrizione}" if ev.descrizione else ev.nome,
                    "docente": ev.docente or "",
                }
                for ev in eventi
                if ev.tipo in ("Avviso", "Verifica")
            ]
        except Exception as e:
            print(f"[NUVOLA] Errore recupero promemoria {self.nome}: {e}")
            return []

    def fetch_registro(self, giorni: int = 0) -> List[Dict[str, Any]]:
        client = self.get_client()
        if not client:
            return []
        alunno_id = self._get_alunno_id()
        if not alunno_id:
            return []

        registro = []
        finestra = max(14, giorni) if giorni > 0 else 14
        oggi = date.today()
        for delta in range(finestra):
            giorno = oggi - timedelta(days=delta)
            data_param = giorno.strftime("%d-%m-%Y")
            try:
                ore = client.get_argomenti_lezione(alunno_id, data_param)
                for o in ore:
                    for arg in o.argomenti:
                        registro.append({
                            "datGiorno": str(o.giorno)[:10],
                            "ora": int(o.numero_ora),
                            "materia": arg.materia or "Materia",
                            "docente": arg.docente or "",
                        })
            except Exception:
                continue
        return registro

    def fetch_orario(self) -> List[Dict[str, Any]]:
        from orario_utils import ricostruisci_orario
        return ricostruisci_orario(self.fetch_registro())

    def fetch_medie(self, giorni: int = 0) -> Optional[Dict[str, Any]]:
        client = self.get_client()
        if not client:
            return None
        alunno_id = self._get_alunno_id()
        if not alunno_id:
            return None

        try:
            frazioni = client.get_frazioni_temporali(alunno_id)
            frazione_corrente = next((f for f in frazioni if f.corrente), frazioni[0] if frazioni else None)
            if not frazione_corrente:
                return None

            materie = client.get_voti_materie(alunno_id, frazione_corrente.id)
            medie_materie: Dict[str, Any] = {}
            somma = 0.0
            conteggio = 0
            for m in materie:
                if m.media_float is not None:
                    medie_materie[m.materia] = str(m.media)
                    somma += m.media_float
                    conteggio += 1

            generale = f"{somma / conteggio:.2f}" if conteggio > 0 else None
            return {"generale": generale, "materie": medie_materie}
        except Exception as e:
            print(f"[NUVOLA] Errore recupero medie {self.nome}: {e}")
            return None
