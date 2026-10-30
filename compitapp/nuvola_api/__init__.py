"""
Nuvola API - Client indipendente per il registro elettronico Nuvola (Madisoft S.p.A.)
"""

from .client import NuvolaClient
from .exceptions import (
    NuvolaAPIError,
    NuvolaAuthError,
    NuvolaError,
    NuvolaNetworkError,
    NuvolaNotFoundError,
    NuvolaPermissionError,
)
from .models import (
    Alunno,
    ArgomentoLezione,
    Assenza,
    Compito,
    ConteggioNotifiche,
    EventoClasse,
    FrazioneTemporale,
    MateriaVoti,
    Nota,
    OraLezione,
    Pagamento,
    VotoDettaglio,
    VotoSintetico,
)

__version__ = "1.0.0"
__all__ = [
    "NuvolaClient",
    "NuvolaError",
    "NuvolaAPIError",
    "NuvolaAuthError",
    "NuvolaPermissionError",
    "NuvolaNotFoundError",
    "NuvolaNetworkError",
    "Alunno",
    "Compito",
    "ArgomentoLezione",
    "OraLezione",
    "EventoClasse",
    "FrazioneTemporale",
    "MateriaVoti",
    "VotoSintetico",
    "VotoDettaglio",
    "Assenza",
    "Nota",
    "ConteggioNotifiche",
    "Pagamento",
]
