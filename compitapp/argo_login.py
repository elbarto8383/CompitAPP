"""Login ad Argo (portale famiglia / DiDUP) con codice scuola, utente e password.

Fa gli stessi passaggi della libreria `argofamiglia` (OAuth2 con PKCE, come l'app DiDUP) ma segue anche
la pagina intermedia che Argo ora mostra al posto dell'ultimo reindirizzamento: «Accesso completato ...
Continua». La libreria, ferma al 2023, cercava l'intestazione Location in quella pagina, non la trovava
e il login falliva con l'errore `'location'`.

Nei messaggi di errore e nel registro non finiscono mai password, codici di accesso o token: gli indirizzi
vengono ridotti a host, percorso e NOMI dei parametri.
"""
import base64
import html
import re
import secrets
from hashlib import sha256
from urllib.parse import parse_qs, urljoin, urlsplit

import requests

try:  # stessi valori della libreria, cosi' restano allineati
    from argofamiglia import auth as _auth
    from argofamiglia.CONSTANTS import ENDPOINT, USER_AGENT
    CHALLENGE_URL = _auth.CHALLENGE_URL
    LOGIN_URL = _auth.LOGIN_URL
    TOKEN_URL = _auth.TOKEN_URL
    REDIRECT_URI = _auth.REDIRECT_URI
    CLIENT_ID = _auth.CLIENT_ID
except Exception:  # pragma: no cover
    CHALLENGE_URL = "https://auth.portaleargo.it/oauth2/auth"
    LOGIN_URL = "https://www.portaleargo.it/auth/sso/login"
    TOKEN_URL = "https://auth.portaleargo.it/oauth2/token"
    REDIRECT_URI = "it.argosoft.didup.famiglia.new://login-callback"
    CLIENT_ID = "72fd6dea-d0ab-4bb9-8eaa-3ac24c84886c"
    ENDPOINT = "https://www.portaleargo.it/famiglia/api/rest/"
    USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/106.0.0.0 Safari/537.36")

MAX_PASSAGGI = 15
_CODICE_RE = re.compile(r"[?&#]code=([0-9a-zA-Z._\-]+)")
_SCHEMA_APP_RE = re.compile(r"""[A-Za-z][A-Za-z0-9+.\-]*://login-callback\?[^"'\s<>\\]+""")
_META_REFRESH_RE = re.compile(r"""<meta[^>]+http-equiv\s*=\s*["']?refresh["']?[^>]*content\s*=\s*["'][^"']*?url\s*=\s*([^"'>\s]+)""", re.I)
_JS_LOCATION_RE = re.compile(r"""(?:location(?:\.href)?\s*=\s*|location\.(?:replace|assign)\(\s*)["']([^"']+)["']""", re.I)
_ANCHOR_RE = re.compile(r"""<a\b[^>]*\bhref\s*=\s*["']([^"']+)["'][^>]*>(.*?)</a>""", re.I | re.S)


class ArgoLoginError(Exception):
    """Login ad Argo non riuscito: il messaggio e' pensato per essere letto da una persona."""


def _sicuro(url):
    """Indirizzo senza valori: host + percorso + NOMI dei parametri (mai codici o token)."""
    p = urlsplit(url or "")
    nomi = ",".join(sorted(parse_qs(p.query).keys()))
    base = f"{p.scheme}://{p.netloc}{p.path}" if p.scheme else (url or "")[:80]
    return base + (f" [parametri: {nomi}]" if nomi else "")


def _codice(url):
    m = _CODICE_RE.search(url or "")
    return m.group(1) if m else None


def _decodifica(testo):
    t = html.unescape(testo or "")
    for a, b in (("\\/", "/"), ("\\u0026", "&"), ("\\u003d", "="), ("\\x26", "&"), ("\\x3d", "=")):
        t = t.replace(a, b)
    return t


def _prossimo_indirizzo(testo, base):
    """Cerca nella pagina intermedia dove Argo manda l'app: l'indirizzo dell'app con il codice,
    un meta refresh, uno script con location=..., oppure il link «Continua». None se non trova niente."""
    t = _decodifica(testo)
    candidati = [m.group(0) for m in _SCHEMA_APP_RE.finditer(t)]
    candidati += [urljoin(base, m.group(1)) for m in _META_REFRESH_RE.finditer(t)]
    candidati += [urljoin(base, m.group(1)) for m in _JS_LOCATION_RE.finditer(t)]
    for href, etichetta in _ANCHOR_RE.findall(t):
        if re.search(r"continu|prosegui|torna|app", re.sub(r"<[^>]+>", " ", etichetta), re.I) or "login-callback" in href:
            candidati.append(urljoin(base, href))
    visti = []
    for c in candidati:
        if c not in visti:
            visti.append(c)
    for c in visti:             # prima chi contiene gia' il codice
        if _codice(c):
            return c
    for c in visti:
        if c.startswith(("http://", "https://")):
            return c
    return None


def _descrivi(r):
    """Breve descrizione della pagina ricevuta (titolo e inizio del testo), per i messaggi di errore."""
    testo = r.text or ""
    m = re.search(r"<title[^>]*>(.*?)</title>", testo, re.I | re.S)
    titolo = re.sub(r"\s+", " ", m.group(1)).strip()[:80] if m else "senza titolo"
    pulito = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", testo, flags=re.S | re.I)
    pulito = re.sub(r"\s+", " ", html.unescape(pulito)).strip()[:140]
    return f"HTTP {r.status_code}, «{titolo}»: {pulito}"


def login(school, username, password, timeout=30, log=None):
    """Login con utente e password. Ritorna (token, tokens) come `codeChallengeLogin` della libreria:
    `token` e' l'x-auth-token del primo profilo, `tokens` contiene access_token e refresh_token.
    `log`, se dato, riceve una riga per passaggio (senza dati sensibili)."""
    def nota(testo):
        if log:
            log(testo)

    verifier = secrets.token_hex(64)
    challenge = base64.urlsafe_b64encode(sha256(verifier.encode()).digest()).replace(b"=", b"").decode()
    params = {
        "redirect_uri": REDIRECT_URI, "client_id": CLIENT_ID, "response_type": "code", "prompt": "login",
        "state": secrets.token_urlsafe(32), "scope": "openid offline profile user.roles argo",
        "code_challenge": challenge, "code_challenge_method": "S256",
    }
    s = requests.Session()

    r = s.get(CHALLENGE_URL, params=params, timeout=timeout)
    nota(f"1 richiesta di accesso: HTTP {r.status_code} {_sicuro(r.url)}")
    m = re.search(r"login_challenge=([0-9a-f]+)", r.url)
    if not m:
        raise ArgoLoginError(f"Argo non ha avviato il login (manca login_challenge). {_descrivi(r)}")

    dati = {"challenge": m.group(1), "client_id": CLIENT_ID, "prefill": "true", "famiglia_customer_code": school,
            "username": username, "password": password, "login": "true"}
    r = s.post(LOGIN_URL, data=dati, allow_redirects=False, timeout=timeout)
    nota(f"2 invio credenziali: HTTP {r.status_code} Location: {'si' if 'Location' in r.headers else 'no'}")
    if "Location" not in r.headers:
        raise ArgoLoginError("Argo ha rifiutato le credenziali (codice scuola, utente o password): "
                             "controlla di riuscire ad accedere al portale con gli stessi dati")

    loc = urljoin(r.url, r.headers["Location"])
    visitati = set()
    for passo in range(3, MAX_PASSAGGI + 3):
        codice = _codice(loc)
        if codice:
            nota(f"{passo} trovato il codice di accesso: {_sicuro(loc)}")
            break
        errore = parse_qs(urlsplit(loc).query).get("error")
        if errore:
            raise ArgoLoginError(f"Argo ha rifiutato l'accesso ({errore[0]})")
        if not loc.startswith(("http://", "https://")):
            raise ArgoLoginError(f"Reindirizzamento inatteso verso {_sicuro(loc)}")
        if loc in visitati:
            raise ArgoLoginError(f"Il login di Argo gira in tondo su {_sicuro(loc)}")
        visitati.add(loc)
        r = s.get(loc, allow_redirects=False, timeout=timeout)
        nota(f"{passo} HTTP {r.status_code} {_sicuro(r.url)}")
        if "Location" in r.headers:
            loc = urljoin(r.url, r.headers["Location"])
            continue
        prossimo = _prossimo_indirizzo(r.text, r.url)
        if prossimo is None:
            raise ArgoLoginError("Argo ha risposto con una pagina che non so seguire. " + _descrivi(r))
        nota(f"{passo} pagina intermedia, passaggio successivo: {_sicuro(prossimo)}")
        loc = prossimo
    else:
        raise ArgoLoginError("Troppi passaggi senza arrivare al codice di accesso")

    tokens = s.post(TOKEN_URL, data={
        "code": codice, "grant_type": "authorization_code", "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier, "client_id": CLIENT_ID}, timeout=timeout).json()
    if not isinstance(tokens, dict) or "access_token" not in tokens:
        motivo = tokens.get("error") if isinstance(tokens, dict) else "risposta inattesa"
        raise ArgoLoginError(f"Argo ha rifiutato lo scambio del codice ({motivo})")
    nota("scambio del codice riuscito (token ottenuto)")

    r = requests.post(ENDPOINT + "login", timeout=timeout, headers={
        "User-Agent": USER_AGENT, "Content-Type": "Application/json",
        "Authorization": "Bearer " + tokens["access_token"], "Accept": "Application/json"},
        json={"clientID": secrets.token_urlsafe(64), "lista-x-auth-token": "[]",
              "x-auth-token-corrente": "null", "lista-opzioni-notifiche": "{}"})
    try:
        token = r.json()["data"][0]["token"]
    except Exception:
        raise ArgoLoginError(f"Argo non ha restituito il profilo dopo il login (HTTP {r.status_code})")
    nota("profilo ottenuto (token non mostrato)")
    return token, tokens
