"""
Test offline per l'accesso con SPID/CIE dentro ArgoConnector (sessione, filtro studenti,
compatibilita' con app.py). Nessuna rete: ArgoFamiglia e spid_auth sono sostituiti da finti.
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "compitapp")))

import argo_client
from connectors import ArgoConnector
from connectors import argo as argo_mod


STUDENTE_SPID = {"nome": "Figlio SPID", "codice_scuola": "SG1", "accesso": "spid"}
STUDENTE_PWD = {"nome": "Figlio Pwd", "codice_scuola": "SG1", "username": "u", "password": "p"}


class TestSpidConnector(unittest.TestCase):

    def setUp(self):
        argo_mod._sessions.clear()
        argo_mod._sessioni_creata.clear()

    def test_get_studenti_accetta_spid_senza_username(self):
        raw = ('[{"nome": "A", "codice_scuola": "SG1", "accesso": "spid"},'
               ' {"nome": "B", "codice_scuola": "SG1", "username": "u", "password": "p"},'
               ' {"nome": "C", "codice_scuola": "SG1"},'
               ' {"nome": "D", "accesso": "spid"}]')
        with patch.dict(os.environ, {"STUDENTI": raw}):
            nomi = [s["nome"] for s in argo_client.get_studenti()]
        self.assertEqual(nomi, ["A", "B"])

    def test_get_session_spid_usa_argospid(self):
        with patch.object(argo_mod, "ArgoSpid") as spid_cls, \
                patch.object(argo_mod, "ArgoPassword") as pwd_cls, \
                patch.object(argo_mod, "_scegli_profilo"):
            sess = ArgoConnector(STUDENTE_SPID).get_session()
        spid_cls.assert_called_once_with("SG1", "Figlio SPID")
        pwd_cls.assert_not_called()
        self.assertIs(sess, spid_cls.return_value)

    def test_get_session_password_resta_invariata(self):
        with patch.object(argo_mod, "ArgoSpid") as spid_cls, \
                patch.object(argo_mod, "ArgoPassword") as pwd_cls, \
                patch.object(argo_mod, "_scegli_profilo"):
            ArgoConnector(STUDENTE_PWD).get_session()
        pwd_cls.assert_called_once_with("SG1", "u", "p")
        spid_cls.assert_not_called()

    def test_sessione_spid_si_ricrea_dopo_45_minuti(self):
        with patch.object(argo_mod, "ArgoSpid") as spid_cls, \
                patch.object(argo_mod, "_scegli_profilo"):
            conn = ArgoConnector(STUDENTE_SPID)
            conn.get_session()
            conn.get_session()
            self.assertEqual(spid_cls.call_count, 1)  # ancora fresca: riusata
            argo_mod._sessioni_creata["Figlio SPID"] = time.time() - argo_mod.SPID_ETA_MAX - 1
            conn.get_session()
            self.assertEqual(spid_cls.call_count, 2)  # scaduta: ricreata

    def test_sessione_password_non_scade_per_eta(self):
        with patch.object(argo_mod, "ArgoPassword") as pwd_cls, \
                patch.object(argo_mod, "_scegli_profilo"):
            conn = ArgoConnector(STUDENTE_PWD)
            conn.get_session()
            argo_mod._sessioni_creata["Figlio Pwd"] = time.time() - 10 * 3600
            conn.get_session()
            self.assertEqual(pwd_cls.call_count, 1)

    def test_reset_session_compatibile_con_app(self):
        """app.py fa `from argo_client import _reset_session` e la chiama con il solo nome."""
        from argo_client import _reset_session
        argo_mod._sessions["Figlio SPID"] = MagicMock()
        argo_mod._sessioni_creata["Figlio SPID"] = time.time()
        _reset_session("Figlio SPID")
        self.assertNotIn("Figlio SPID", argo_mod._sessions)
        self.assertNotIn("Figlio SPID", argo_mod._sessioni_creata)

    def test_errore_di_sessione_ritorna_none_e_pulisce(self):
        with patch.object(argo_mod, "ArgoSpid", side_effect=RuntimeError("boom")):
            self.assertIsNone(ArgoConnector(STUDENTE_SPID).get_session())
        self.assertNotIn("Figlio SPID", argo_mod._sessions)


class TestArgoSpidSessione(unittest.TestCase):

    def test_connect_usa_il_token_rinnovato(self):
        """ArgoSpid.connect() deve ottenere il token da spid_auth.rinnova e impostare gli header."""
        fake_spid_auth = MagicMock()
        fake_spid_auth.rinnova.return_value = {"access_token": "ACC"}
        risposta = MagicMock()
        risposta.json.return_value = {"data": [{"token": "TOK"}]}
        with patch.dict(sys.modules, {"spid_auth": fake_spid_auth}), \
                patch.object(argo_mod.requests, "post", return_value=risposta) as post, \
                patch.object(argo_mod.ArgoFamiglia, "__init__", lambda self, school, user, pwd: setattr(self, "_ArgoFamiglia__school", school)):
            s = argo_mod.ArgoSpid("SG1", "Figlio SPID")
            s.connect()
        fake_spid_auth.rinnova.assert_called_once_with("Figlio SPID")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer ACC")
        self.assertEqual(s._ArgoFamiglia__token, "TOK")
        self.assertEqual(s._ArgoFamiglia__headers["x-cod-min"], "SG1")
        self.assertEqual(s._ArgoFamiglia__headers["x-auth-token"], "TOK")


if __name__ == "__main__":
    unittest.main()
