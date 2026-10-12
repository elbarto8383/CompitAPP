"""
Eccezioni personalizzate per il client delle API di Nuvola.
"""

from typing import Optional


class NuvolaError(Exception):
    """Classe base per tutte le eccezioni sollevate dal client Nuvola."""
    pass


class NuvolaNetworkError(NuvolaError):
    """Sollevata in caso di errori di connettività di rete o timeout."""
    pass


class NuvolaAPIError(NuvolaError):
    """Sollevata quando l'API restituisce un errore HTTP o un messaggio di errore."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        if self.status_code:
            return f"[HTTP {self.status_code}] {super().__str__()}"
        return super().__str__()


class NuvolaAuthError(NuvolaAPIError):
    """Sollevata in caso di fallimento dell'autenticazione, credenziali non valide o token scaduto."""
    pass


class NuvolaPermissionError(NuvolaAPIError):
    """Sollevata quando l'utente non ha i permessi per accedere alla risorsa (HTTP 403)."""
    pass


class NuvolaNotFoundError(NuvolaAPIError):
    """Sollevata quando la risorsa o l'endpoint specificato non esiste (HTTP 404)."""
    pass
