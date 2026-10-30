"""
Interfaccia client e routing verso i connettori di registro.
Mantiene la retrocompatibilita' completa per le funzioni invocate da scheduler, app e bot.
"""

import json
import os
from typing import Any, Dict, List, Optional

from connectors import ArgoConnector, BaseConnector, NuvolaConnector, get_connector
from connectors.argo import _reset_session as _reset_connector_session


def _valido(s: Dict[str, Any]) -> bool:
    if str(s.get('registro') or 'argo').strip().lower() == 'nuvola':
        return bool(s.get('username'))
    return bool(s.get('codice_scuola') and (s.get('username') or s.get('accesso') == 'spid'))


def get_studenti() -> List[Dict[str, Any]]:
    """Estrae l'elenco degli studenti configurati dalla variabile di ambiente STUDENTI.
    Argo: codice_scuola e, con password, username (con SPID non serve). Nuvola: username."""
    raw = os.environ.get('STUDENTI', '[]')
    try:
        return [s for s in json.loads(raw) if _valido(s)]
    except Exception as e:
        print(f"[ARGO] Errore parsing STUDENTI: {e}")
        return []


def _reset_session(nome: str) -> None:
    """Compatibilita': app.py la importa per ricollegare un accesso SPID."""
    _reset_connector_session(nome)


def get_session(studente: Dict[str, Any]) -> Any:
    """Restituisce la sessione nativa del connettore se supportata (Argo)."""
    conn = get_connector(studente)
    if isinstance(conn, ArgoConnector):
        return conn.get_session()
    return None


def fetch_dashboard(studente: Dict[str, Any], giorni: int = 0) -> Optional[Dict[str, Any]]:
    return get_connector(studente).fetch_dashboard(giorni=giorni)


def fetch_compiti(studente: Dict[str, Any]) -> Dict[str, Any]:
    return get_connector(studente).fetch_compiti()


def fetch_voti(studente: Dict[str, Any], giorni: int = 0) -> List[Dict[str, Any]]:
    return get_connector(studente).fetch_voti(giorni=giorni)


def fetch_assenze(studente: Dict[str, Any], giorni: int = 0) -> List[Dict[str, Any]]:
    return get_connector(studente).fetch_assenze(giorni=giorni)


def fetch_note(studente: Dict[str, Any], giorni: int = 0) -> List[Dict[str, Any]]:
    return get_connector(studente).fetch_note(giorni=giorni)


def fetch_bacheca(studente: Dict[str, Any], giorni: int = 0) -> List[Dict[str, Any]]:
    return get_connector(studente).fetch_bacheca(giorni=giorni)


def fetch_argomenti(studente: Dict[str, Any], giorni: int = 0) -> List[Dict[str, Any]]:
    return get_connector(studente).fetch_argomenti(giorni=giorni)


def fetch_registro(studente: Dict[str, Any], giorni: int = 0) -> List[Dict[str, Any]]:
    return get_connector(studente).fetch_registro(giorni=giorni)


def fetch_orario(studente: Dict[str, Any]) -> List[Dict[str, Any]]:
    return get_connector(studente).fetch_orario()


def fetch_promemoria(studente: Dict[str, Any], giorni: int = 0) -> List[Dict[str, Any]]:
    return get_connector(studente).fetch_promemoria(giorni=giorni)


def fetch_medie(studente: Dict[str, Any], giorni: int = 0) -> Optional[Dict[str, Any]]:
    return get_connector(studente).fetch_medie(giorni=giorni)


__all__ = [
    "get_studenti",
    "get_session",
    "get_connector",
    "fetch_dashboard",
    "fetch_compiti",
    "fetch_voti",
    "fetch_assenze",
    "fetch_note",
    "fetch_bacheca",
    "fetch_argomenti",
    "fetch_registro",
    "fetch_orario",
    "fetch_promemoria",
    "fetch_medie",
    "BaseConnector",
    "ArgoConnector",
    "NuvolaConnector",
]
