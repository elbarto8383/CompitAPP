"""
Test offline per argo_login: il login ad Argo deve funzionare sia con il reindirizzamento diretto
sia con la pagina intermedia «Accesso completato ... Continua» (errore 'location' di fine ottobre 2026),
e non deve mai far uscire password, codici o token nei messaggi.
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "compitapp")))

import argo_login
from argo_login import ArgoLoginError

APP = "it.argosoft.didup.famiglia.new://login-callback"
CODICE = "CODICE-SEGRETO-123"
PASSWORD = "PASSWORD-SEGRETA"
TOKEN_PROFILO = "TOKEN-PROFILO-XYZ"
ACCESS = "ACCESS-TOKEN-ABC"


class Resp:
    def __init__(self, url, status=200, headers=None, text="", json_data=None):
        self.url, self.status_code, self.headers, self.text, self._json = url, status, headers or {}, text, json_data

    def json(self):
        return self._json


def redirect(url, verso):
    return Resp(url, 302, {"Location": verso})


def pagina(url, html):
    return Resp(url, 200, {"Content-Type": "text/html"}, html)


class FakeSession:
    """Argo finto: `percorso` associa un indirizzo (senza query) alla risposta da dare."""

    def __init__(self, percorso, credenziali_ok=True, token_ok=True):
        self.percorso, self.credenziali_ok, self.token_ok, self.visti = percorso, credenziali_ok, token_ok, []

    def get(self, url, params=None, allow_redirects=True, timeout=0):
        if params:   # richiesta di accesso iniziale
            return pagina("https://www.portaleargo.it/auth/sso/login/?login_challenge=abc123", "<title>Accedi</title>")
        self.visti.append(url)
        chiave = url.split("?")[0]
        if chiave not in self.percorso:
            raise AssertionError(f"indirizzo non previsto: {url}")
        return self.percorso[chiave]

    def post(self, url, data=None, allow_redirects=True, timeout=0):
        if url == argo_login.LOGIN_URL:
            assert data["famiglia_customer_code"] == "SG1" and data["password"] == PASSWORD
            if not self.credenziali_ok:
                return Resp(url, 200, {}, "<title>Accedi</title>")
            return redirect(url, "https://auth.portaleargo.it/oauth2/auth?login_verifier=ZZZ")
        if url == argo_login.TOKEN_URL:
            assert data["code"] == CODICE and data["grant_type"] == "authorization_code"
            return Resp(url, 200, json_data={"access_token": ACCESS, "refresh_token": "R"} if self.token_ok
                        else {"error": "invalid_grant"})
        raise AssertionError(url)


def esegui(percorso, **kw):
    sess = FakeSession(percorso, **{k: v for k, v in kw.items() if k in ("credenziali_ok", "token_ok")})
    profilo = Resp("x", json_data={"data": [{"token": TOKEN_PROFILO}]})
    righe = []
    with patch.object(argo_login.requests, "Session", return_value=sess), \
            patch.object(argo_login.requests, "post", return_value=profilo):
        risultato = argo_login.login("SG1", "utente", PASSWORD, log=righe.append)
    return risultato, righe, sess


A = "https://auth.portaleargo.it/oauth2/auth"
CONSENT = "https://www.portaleargo.it/auth/sso/consent"


class TestLoginArgo(unittest.TestCase):

    def controlla(self, risultato):
        token, tokens = risultato
        self.assertEqual(token, TOKEN_PROFILO)
        self.assertEqual(tokens["access_token"], ACCESS)

    def test_flusso_normale_con_reindirizzamento_diretto(self):
        r, righe, _ = esegui({A: redirect(A, f"{APP}?code={CODICE}&state=S")})
        self.controlla(r)

    def test_pagina_intermedia_con_link_continua_verso_l_app(self):
        html = f'<h1>Accesso completato</h1><a class="btn" href="{APP}?code={CODICE}&amp;state=S">Continua</a>'
        r, righe, _ = esegui({A: redirect(A, CONSENT + "?consent_challenge=c"), CONSENT: pagina(CONSENT, html)})
        self.controlla(r)
        self.assertTrue(any("pagina intermedia" in x for x in righe))

    def test_pagina_intermedia_con_meta_refresh_e_un_passaggio_http(self):
        html = '<meta http-equiv="refresh" content="0; url=https://www.portaleargo.it/auth/sso/fine?x=1">Continua'
        fine = "https://www.portaleargo.it/auth/sso/fine"
        r, _, _ = esegui({A: redirect(A, CONSENT + "?c=1"), CONSENT: pagina(CONSENT, html),
                          fine: redirect(fine, f"{APP}?code={CODICE}&state=S")})
        self.controlla(r)

    def test_pagina_intermedia_con_javascript_e_caratteri_escapati(self):
        js = f"<script>setTimeout(function(){{ window.location.href = '{APP}?code={CODICE}\\u0026state=S'; }}, 100);</script>"
        r, _, _ = esegui({A: redirect(A, CONSENT + "?c=1"), CONSENT: pagina(CONSENT, js)})
        self.controlla(r)

    def test_pagina_inattesa_da_errore_chiaro_senza_segreti(self):
        html = "<title>Manutenzione</title><p>Servizio non disponibile, riprova tra poco.</p>"
        with self.assertRaises(ArgoLoginError) as cm:
            esegui({A: redirect(A, CONSENT + "?consent_challenge=SEGRETO"), CONSENT: pagina(CONSENT, html)})
        msg = str(cm.exception)
        self.assertIn("Manutenzione", msg)
        for segreto in (PASSWORD, "SEGRETO", CODICE):
            self.assertNotIn(segreto, msg)

    def test_credenziali_rifiutate(self):
        with self.assertRaises(ArgoLoginError) as cm:
            esegui({}, credenziali_ok=False)
        self.assertIn("credenziali", str(cm.exception))
        self.assertNotIn(PASSWORD, str(cm.exception))

    def test_scambio_del_codice_rifiutato(self):
        with self.assertRaises(ArgoLoginError) as cm:
            esegui({A: redirect(A, f"{APP}?code={CODICE}&state=S")}, token_ok=False)
        self.assertIn("invalid_grant", str(cm.exception))

    def test_reindirizzamento_con_errore_dell_app(self):
        with self.assertRaises(ArgoLoginError) as cm:
            esegui({A: redirect(A, f"{APP}?error=access_denied")})
        self.assertIn("access_denied", str(cm.exception))

    def test_loop_infinito_si_ferma(self):
        with self.assertRaises(ArgoLoginError):
            esegui({A: redirect(A, CONSENT + "?c=1"), CONSENT: redirect(CONSENT, A + "?x=1")})

    def test_il_registro_dei_passaggi_non_contiene_segreti(self):
        html = f'<a href="{APP}?code={CODICE}&amp;state=S">Continua</a>'
        _, righe, _ = esegui({A: redirect(A, CONSENT + "?consent_challenge=SEGRETO"), CONSENT: pagina(CONSENT, html)})
        testo = "\n".join(righe)
        for segreto in (PASSWORD, "SEGRETO", CODICE, ACCESS, TOKEN_PROFILO, "utente"):
            self.assertNotIn(segreto, testo)
        self.assertIn("codice di accesso", testo)


if __name__ == "__main__":
    unittest.main()


from typing import Any
from connectors import argo as argo_mod


@unittest.skipIf(argo_mod.ArgoFamiglia is Any, "libreria argofamiglia non installata")
class TestSessioneArgoPassword(unittest.TestCase):

    def test_connect_imposta_token_e_intestazioni_come_la_libreria(self):
        with patch.object(argo_login, "login", return_value=(TOKEN_PROFILO, {"access_token": ACCESS, "refresh_token": "R"})) as l:
            s = argo_mod.ArgoPassword("SG1", "utente", PASSWORD)
        l.assert_called_once_with("SG1", "utente", PASSWORD)
        self.assertEqual(s._ArgoFamiglia__token, TOKEN_PROFILO)
        self.assertEqual(s._ArgoFamiglia__login_data["refresh_token"], "R")
        h = s._ArgoFamiglia__headers
        self.assertEqual(h["Authorization"], "Bearer " + ACCESS)
        self.assertEqual((h["x-cod-min"], h["x-auth-token"]), ("SG1", TOKEN_PROFILO))

    def test_errore_di_login_arriva_a_get_session_come_messaggio_chiaro(self):
        argo_mod._sessions.clear()
        studente = {"nome": "Luigi", "codice_scuola": "SG1", "username": "u", "password": PASSWORD}
        with patch.object(argo_login, "login", side_effect=ArgoLoginError("Argo ha rifiutato le credenziali")):
            import io, contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                sess = argo_mod.ArgoConnector(studente).get_session()
        self.assertIsNone(sess)
        self.assertIn("Argo ha rifiutato le credenziali", buf.getvalue())
        self.assertNotIn(PASSWORD, buf.getvalue())
