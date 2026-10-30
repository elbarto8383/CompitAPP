"""
Modulo connettori per i registri elettronici supportati da CompitAPP.
"""

from typing import Any, Dict

from .base import BaseConnector
from .argo import ArgoConnector

_connectors: Dict[str, BaseConnector] = {}


def get_connector(studente: Dict[str, Any]) -> BaseConnector:
    """Restituisce l'istanza del connettore associato allo studente.
    Valore predefinito: ArgoConnector."""
    nome = studente.get("nome", "default")
    if nome not in _connectors:
        _connectors[nome] = ArgoConnector(studente)
    return _connectors[nome]


__all__ = ["BaseConnector", "ArgoConnector", "get_connector"]
