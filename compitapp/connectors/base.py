"""
Interfaccia base per i connettori dei registri elettronici scolastici.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseConnector(ABC):
    """Classe base astratta che definisce il contratto per i connettori di registro."""

    def __init__(self, studente: Dict[str, Any]):
        self.studente = studente
        self.nome: str = studente.get("nome", "default")

    @abstractmethod
    def fetch_dashboard(self, giorni: int = 0) -> Optional[Dict[str, Any]]:
        """Recupera la dashboard o i dati aggregati del registro."""
        pass

    @abstractmethod
    def fetch_compiti(self) -> Dict[str, Any]:
        """Recupera l'elenco dei compiti assegnati."""
        pass

    @abstractmethod
    def fetch_voti(self, giorni: int = 0) -> List[Dict[str, Any]]:
        """Recupera i voti dello studente."""
        pass

    @abstractmethod
    def fetch_assenze(self, giorni: int = 0) -> List[Dict[str, Any]]:
        """Recupera assenze, ritardi e uscite anticipate."""
        pass

    @abstractmethod
    def fetch_note(self, giorni: int = 0) -> List[Dict[str, Any]]:
        """Recupera le note disciplinari."""
        pass

    @abstractmethod
    def fetch_bacheca(self, giorni: int = 0) -> List[Dict[str, Any]]:
        """Recupera le comunicazioni e circolari della bacheca scolastica."""
        pass

    @abstractmethod
    def fetch_argomenti(self, giorni: int = 0) -> List[Dict[str, Any]]:
        """Recupera gli argomenti delle lezioni svolte."""
        pass

    @abstractmethod
    def fetch_promemoria(self, giorni: int = 0) -> List[Dict[str, Any]]:
        """Recupera i promemoria annotati dai docenti."""
        pass

    @abstractmethod
    def fetch_registro(self, giorni: int = 0) -> List[Dict[str, Any]]:
        """Recupera le lezioni registrate per la ricostruzione dell'orario."""
        pass

    @abstractmethod
    def fetch_orario(self) -> List[Dict[str, Any]]:
        """Recupera l'orario settimanale delle lezioni."""
        pass

    @abstractmethod
    def fetch_medie(self, giorni: int = 0) -> Optional[Dict[str, Any]]:
        """Recupera le medie ufficiali calcolate dal registro (generale e per materia)."""
        pass
