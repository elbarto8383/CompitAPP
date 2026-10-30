"""
Modulo connettori per i registri elettronici supportati da CompitAPP.
"""

from typing import Any, Dict

from .base import BaseConnector
from .argo import ArgoConnector
from .nuvola import NuvolaConnector

_connectors: Dict[str, BaseConnector] = {}


def get_connector(studente: Dict[str, Any]) -> BaseConnector:
    """Restituisce l'istanza del connettore associato allo studente in base al registro configurato.
    Valore predefinito: ArgoConnector."""
    nome = studente.get("nome", "default")
    registro = str(studente.get("registro") or "argo").strip().lower()

    if nome not in _connectors:
        if registro == "nuvola":
            _connectors[nome] = NuvolaConnector(studente)
        else:
            _connectors[nome] = ArgoConnector(studente)
    return _connectors[nome]


__all__ = ["BaseConnector", "ArgoConnector", "NuvolaConnector", "get_connector"]
