"""
Client REST principale per le API di Nuvola (Madisoft S.p.A.).
Supporta la gestione automatica dei token, rinnovo con refresh token,
caching su disco e deserializzazione opzionale nei modelli tipizzati.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Union

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
)

logger = logging.getLogger("nuvola_api")


class NuvolaClient:
    """
    Client HTTP indipendente per il registro elettronico Nuvola.
    
    Zero dipendenze esterne: utilizza esclusivamente i moduli standard di Python.
    """

    BASE_URL = "https://nuvola.madisoft.it/api-studente/v1"
    DEFAULT_USER_AGENT = "okhttp/4.9.2"
    DEFAULT_TIMEOUT = 12

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        session_file: Optional[str] = "nuvola_session.json",
        timeout: int = DEFAULT_TIMEOUT,
        user_agent: str = DEFAULT_USER_AGENT,
        auto_save_session: bool = True,
    ):
        """
        Inizializza il client Nuvola.

        :param username: Nome utente Nuvola (opzionale se già presente una sessione valida).
        :param password: Password dell'utenza.
        :param session_file: Percorso del file JSON su disco in cui persistere i token.
        :param timeout: Timeout in secondi per le chiamate HTTP.
        :param user_agent: Stringa User-Agent inviata negli header (default: okhttp dell'app mobile).
        :param auto_save_session: Se abilitato, salva automaticamente i token su disco dopo login e refresh.
        """
        self.username = username
        self.password = password
        self.session_file = session_file
        self.timeout = timeout
        self.user_agent = user_agent
        self.auto_save_session = auto_save_session
        self.session_data: Dict[str, Any] = self._load_session()

    # -------------------------------------------------------------------------
    # Gestione Sessione & Token
    # -------------------------------------------------------------------------

    def _load_session(self) -> Dict[str, Any]:
        """Carica i dati di sessione dal file locale se esistente."""
        if self.session_file and os.path.exists(self.session_file):
            try:
                with open(self.session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if self.username and data.get("username") and data.get("username") != self.username:
                        logger.warning("Sessione su disco appartenente a un altro utente, invalidata: %s", self.session_file)
                        return {}
                    return data
            except Exception as e:
                logger.warning("Impossibile caricare il file di sessione %s: %s", self.session_file, e)
        return {}

    def _save_session(self) -> None:
        """Salva i dati di sessione su disco se configurato, con permessi 600 (solo owner)."""
        if not self.auto_save_session or not self.session_file:
            return
        try:
            dir_name = os.path.dirname(self.session_file)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            fd = os.open(self.session_file, flags, 0o600)
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(self.session_data, f, indent=2)
            try:
                os.chmod(self.session_file, 0o600)
            except Exception:
                pass
        except Exception as e:
            logger.error("Errore durante il salvataggio della sessione su %s: %s", self.session_file, e)

    def is_authenticated(self) -> bool:
        """Verifica se è disponibile un token di sessione (non ancora scaduto o rinnovabile)."""
        return bool(self.session_data.get("token") or self.session_data.get("refreshToken"))

    def login(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        Effettua il login nativo tramite API mobile (bypass SPID/CIE).
        
        :return: True se il login ha avuto successo, altrimenti solleva un'eccezione o restituisce False.
        """
        u = username or self.username
        p = password or self.password
        if not u or not p:
            raise NuvolaAuthError("Credenziali username e password necessarie per il login iniziale.")

        url = f"{self.BASE_URL}/login"
        payload = json.dumps({"username": u, "password": p}).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    now = time.time()
                    self.session_data = {
                        "username": u,
                        "token": data.get("token"),
                        "refreshToken": data.get("refreshToken"),
                        "idAnagrafica": data.get("idAnagrafica"),
                        "nome": data.get("nome"),
                        "cognome": data.get("cognome"),
                        "codiceCliente": data.get("codiceCliente"),
                        "expires_at": now + 1740,  # 29 minuti (durata effettiva 30 min)
                    }
                    self._save_session()
                    return True
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            if e.code == 401:
                raise NuvolaAuthError(f"Login non riuscito: credenziali non valide ({err_body})", status_code=401, response_body=err_body)
            raise NuvolaAPIError(f"Errore HTTP durante il login ({e.code}): {err_body}", status_code=e.code, response_body=err_body)
        except urllib.error.URLError as e:
            raise NuvolaNetworkError(f"Errore di rete durante il login: {e.reason}")
        except Exception as e:
            raise NuvolaError(f"Errore imprevisto durante il login: {e}")

        return False

    def refresh_token(self) -> bool:
        """
        Rinnova il token JWT scaduto utilizzando il refresh token.
        
        NOTA CRITICA: il body inviato a Nuvola DEVE avere il campo 'refresh_token' (snake_case),
        nonostante la risposta del login restituisca 'refreshToken' (camelCase).
        """
        refresh_tk = self.session_data.get("refreshToken")
        if not refresh_tk:
            logger.debug("Nessun refreshToken disponibile per il rinnovo.")
            return False

        url = f"{self.BASE_URL}/refresh-token"
        payload = json.dumps({"refresh_token": refresh_tk}).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    now = time.time()
                    self.session_data["token"] = data.get("token")
                    if data.get("refreshToken"):
                        self.session_data["refreshToken"] = data.get("refreshToken")
                    self.session_data["expires_at"] = now + 1740
                    self._save_session()
                    return True
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.warning("Rinnovo del token fallito (HTTP %d): %s", e.code, err_body)
            return False
        except Exception as e:
            logger.warning("Eccezione durante il refresh del token: %s", e)
            return False

        return False

    def get_valid_token(self) -> str:
        """
        Restituisce un Bearer Token valido. Se scaduto o in scadenza,
        tenta il refresh trasparente o il re-login con le credenziali fornite.
        """
        now = time.time()
        token = self.session_data.get("token")
        expires_at = self.session_data.get("expires_at", 0)

        # 1. Token ancora valido (con margine di sicurezza di 60 secondi)
        if token and now < (expires_at - 60):
            return token

        # 2. Tentativo di rinnovo con Refresh Token
        if self.session_data.get("refreshToken") and self.refresh_token():
            tok = self.session_data.get("token")
            if tok:
                return tok

        # 3. Fallback con login completo se fornite le credenziali
        if self.username and self.password and self.login():
            tok = self.session_data.get("token")
            if tok:
                return tok

        raise NuvolaAuthError("Autenticazione richiesta: sessione scaduta e impossibile rinnovare il token.")

    # -------------------------------------------------------------------------
    # Esecutore Richieste HTTP
    # -------------------------------------------------------------------------

    def raw_request(
        self,
        endpoint: str,
        method: str = "GET",
        query_params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        retry_on_401: bool = True,
    ) -> Any:
        """
        Invia una richiesta HTTP all'API di Nuvola, gestendo Bearer token e retry automatico.
        """
        token = self.get_valid_token()
        url = f"{self.BASE_URL}{endpoint}"
        if query_params:
            url += "?" + urllib.parse.urlencode(query_params)

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }

        data_bytes = None
        if json_body is not None:
            headers["Content-Type"] = "application/json"
            data_bytes = json.dumps(json_body).encode("utf-8")

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                content = resp.read().decode("utf-8")
                return json.loads(content) if content else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")

            # In caso di 401 imprevisto, tentiamo il rinnovo del token una volta
            if e.code == 401 and retry_on_401:
                logger.info("Ricevuto HTTP 401. Tentativo di refresh del token e retry della chiamata...")
                refreshed = self.refresh_token() or (bool(self.username and self.password) and self.login())
                if refreshed:
                    return self.raw_request(
                        endpoint=endpoint,
                        method=method,
                        query_params=query_params,
                        json_body=json_body,
                        retry_on_401=False,
                    )
                raise NuvolaAuthError(f"Sessione non autorizzata (401): {err_body}", status_code=401, response_body=err_body)

            if e.code == 403:
                raise NuvolaPermissionError(f"Accesso negato alla risorsa (403): {err_body}", status_code=403, response_body=err_body)
            if e.code == 404:
                raise NuvolaNotFoundError(f"Risorsa non trovata (404): {err_body}", status_code=404, response_body=err_body)

            raise NuvolaAPIError(f"Errore API Nuvola (HTTP {e.code}): {err_body}", status_code=e.code, response_body=err_body)
        except urllib.error.URLError as e:
            raise NuvolaNetworkError(f"Errore di connessione verso Nuvola: {e.reason}")

    def get_envelope_values(self, endpoint: str, query_params: Optional[Dict[str, Any]] = None) -> Any:
        """Esegue una GET ed estrae il campo 'valori' dall'involucro standard Nuvola."""
        res = self.raw_request(endpoint, method="GET", query_params=query_params)
        if isinstance(res, dict) and "valori" in res:
            return res.get("valori")
        return res

    # -------------------------------------------------------------------------
    # Metodi di Interrogazione Risorse (High-Level API)
    # -------------------------------------------------------------------------

    def get_alunni(self) -> List[Alunno]:
        """Restituisce la lista degli studenti associati all'account genitore/tutore."""
        items = self.get_envelope_values("/alunni") or []
        return [Alunno.from_dict(it) for it in items]

    def get_alunni_raw(self) -> List[Dict[str, Any]]:
        """Restituisce il payload JSON originale degli studenti."""
        return self.get_envelope_values("/alunni") or []

    def get_compiti(self, alunno_id: int, date_str: str) -> List[Compito]:
        """
        Recupera i compiti per casa assegnati per una data specifica.
        
        :param alunno_id: ID univoco dello studente.
        :param date_str: Data di consegna nel formato DD-MM-YYYY (es. '15-10-2026').
        """
        items = self.get_envelope_values(
            f"/alunno/{alunno_id}/compito/elenco/{date_str}",
            query_params={"contextAlunno": alunno_id}
        ) or []
        return [Compito.from_dict(it) for it in items]

    def get_compiti_raw(self, alunno_id: int, date_str: str) -> List[Dict[str, Any]]:
        return self.get_envelope_values(
            f"/alunno/{alunno_id}/compito/elenco/{date_str}",
            query_params={"contextAlunno": alunno_id}
        ) or []

    def get_argomenti_lezione(self, alunno_id: int, date_str: str) -> List[OraLezione]:
        """
        Recupera l'orario scolastico della giornata e gli argomenti svolti.
        
        :param alunno_id: ID univoco dello studente.
        :param date_str: Data nel formato DD-MM-YYYY.
        """
        items = self.get_envelope_values(
            f"/alunno/{alunno_id}/argomento-lezione/elenco/{date_str}",
            query_params={"contextAlunno": alunno_id}
        ) or []
        return [OraLezione.from_dict(it) for it in items]

    def get_argomenti_lezione_raw(self, alunno_id: int, date_str: str) -> List[Dict[str, Any]]:
        return self.get_envelope_values(
            f"/alunno/{alunno_id}/argomento-lezione/elenco/{date_str}",
            query_params={"contextAlunno": alunno_id}
        ) or []

    def get_eventi_classe(self, alunno_id: int) -> List[EventoClasse]:
        """Recupera il calendario eventi della classe (verifiche, uscite didattiche, avvisi)."""
        items = self.get_envelope_values(
            f"/alunno/{alunno_id}/eventi-classe",
            query_params={"contextAlunno": alunno_id}
        ) or []
        return [EventoClasse.from_dict(it) for it in items]

    def get_frazioni_temporali(self, alunno_id: int) -> List[FrazioneTemporale]:
        """Recupera la suddivisione dell'anno scolastico (1° quadrimestre, 2° quadrimestre, intero anno)."""
        items = self.get_envelope_values(
            f"/alunno/{alunno_id}/frazioni-temporali",
            query_params={"contextAlunno": alunno_id}
        ) or []
        return [FrazioneTemporale.from_dict(it) for it in items]

    def get_voti_materie(self, alunno_id: int, frazione_id: int) -> List[MateriaVoti]:
        """Recupera il riepilogo voti e medie per materia nel periodo specificato."""
        items = self.get_envelope_values(
            f"/alunno/{alunno_id}/frazione-temporale/{frazione_id}/voti/materie",
            query_params={"contextAlunno": alunno_id}
        ) or []
        return [MateriaVoti.from_dict(it) for it in items]

    def get_voti_dettaglio_materia(
        self, alunno_id: int, frazione_id: int, materia_id: int
    ) -> List[VotoDettaglio]:
        """Recupera i singoli voti dettagliati per una specifica materia."""
        items = self.get_envelope_values(
            f"/alunno/{alunno_id}/frazione-temporale/{frazione_id}/voti/materia/{materia_id}",
            query_params={"contextAlunno": alunno_id}
        ) or []
        return [VotoDettaglio.from_dict(it) for it in items]

    def get_tutti_voti(self, alunno_id: int) -> List[VotoDettaglio]:
        """Recupera lo storico di tutti i voti dell'alunno in ordine cronologico."""
        items = self.get_envelope_values(
            f"/alunno/{alunno_id}/voti",
            query_params={"contextAlunno": alunno_id}
        ) or []
        return [VotoDettaglio.from_dict(it) for it in items]

    def get_assenze(self, alunno_id: int) -> List[Assenza]:
        """Recupera lo storico di assenze, ritardi e uscite anticipate."""
        items = self.get_envelope_values(
            f"/alunno/{alunno_id}/assenze",
            query_params={"contextAlunno": alunno_id}
        ) or []
        return [Assenza.from_dict(it) for it in items]

    def get_note(self, alunno_id: int) -> List[Nota]:
        """Recupera le note disciplinari e le annotazioni sul registro."""
        items = self.get_envelope_values(
            f"/alunno/{alunno_id}/note",
            query_params={"contextAlunno": alunno_id}
        ) or []
        return [Nota.from_dict(it) for it in items]

    def get_notifiche_conteggio(self, alunno_id: int) -> ConteggioNotifiche:
        """Recupera il conteggio delle notifiche ed eventi non letti."""
        res = self.raw_request(
            f"/alunno/{alunno_id}/notifiche/conteggio",
            query_params={"contextAlunno": alunno_id}
        )
        return ConteggioNotifiche.from_dict(res)

    def get_pagamenti(self, alunno_id: int) -> List[Pagamento]:
        """Recupera l'elenco dei pagamenti e contributi scolastici PagoPA."""
        items = self.get_envelope_values(
            f"/alunno/{alunno_id}/pagamenti",
            query_params={"contextAlunno": alunno_id}
        ) or []
        return [Pagamento.from_dict(it) for it in items]
