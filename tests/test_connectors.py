"""
Test unitari per l'architettura a connettori (BaseConnector e ArgoConnector).
Esecuzione completamente offline senza rete.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Includi compitapp nel PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "compitapp")))

from connectors import BaseConnector, ArgoConnector, get_connector
import argo_client


class TestConnectorArchitecture(unittest.TestCase):

    def test_base_connector_is_abstract(self):
        """Verifica che BaseConnector non sia istanziabile direttamente senza implementazione."""
        with self.assertRaises(TypeError):
            BaseConnector({"nome": "Test"})

    def test_argo_connector_inheritance(self):
        """Verifica che ArgoConnector erediti da BaseConnector."""
        studente = {
            "nome": "Mario Rossi",
            "codice_scuola": "SG12345",
            "username": "m.rossi",
            "password": "secret"
        }
        conn = ArgoConnector(studente)
        self.assertIsInstance(conn, BaseConnector)
        self.assertEqual(conn.nome, "Mario Rossi")

    def test_get_connector_factory(self):
        """Verifica la factory get_connector e il recupero dell'istanza."""
        studente = {
            "nome": "Luigi Bianchi",
            "codice_scuola": "SG54321",
            "username": "l.bianchi",
            "password": "secret"
        }
        conn1 = get_connector(studente)
        conn2 = get_connector(studente)
        self.assertIsInstance(conn1, ArgoConnector)
        self.assertIs(conn1, conn2)

    def test_argo_client_facade_delegation(self):
        """Verifica che le funzioni di facciata in argo_client deleghino al connettore."""
        studente = {
            "nome": "Anna Verdi",
            "codice_scuola": "SG99999",
            "username": "a.verdi",
            "password": "secret"
        }
        mock_conn = MagicMock(spec=ArgoConnector)
        mock_conn.fetch_compiti.return_value = {"compiti": ["Esercizio 1"]}
        mock_conn.fetch_voti.return_value = [{"materia": "Matematica", "voto": "8"}]
        mock_conn.fetch_assenze.return_value = [{"tipo": "A", "giustificata": True}]
        mock_conn.fetch_note.return_value = [{"testo": "Nota"}]
        mock_conn.fetch_bacheca.return_value = [{"titolo": "Circolare 1"}]
        mock_conn.fetch_argomenti.return_value = [{"argomento": "Frazioni"}]
        mock_conn.fetch_registro.return_value = [{"materia": "Storia"}]
        mock_conn.fetch_orario.return_value = {"lunedi": []}
        mock_conn.fetch_promemoria.return_value = [{"testo": "Portare libro"}]
        mock_conn.fetch_medie.return_value = {"generale": "8.5"}

        with patch("argo_client.get_connector", return_value=mock_conn):
            self.assertEqual(argo_client.fetch_compiti(studente), {"compiti": ["Esercizio 1"]})
            self.assertEqual(argo_client.fetch_voti(studente, giorni=7), [{"materia": "Matematica", "voto": "8"}])
            mock_conn.fetch_voti.assert_called_once_with(giorni=7)

            self.assertEqual(argo_client.fetch_assenze(studente, giorni=5), [{"tipo": "A", "giustificata": True}])
            mock_conn.fetch_assenze.assert_called_once_with(giorni=5)

            self.assertEqual(argo_client.fetch_note(studente), [{"testo": "Nota"}])
            self.assertEqual(argo_client.fetch_bacheca(studente), [{"titolo": "Circolare 1"}])
            self.assertEqual(argo_client.fetch_argomenti(studente), [{"argomento": "Frazioni"}])
            self.assertEqual(argo_client.fetch_registro(studente), [{"materia": "Storia"}])
            self.assertEqual(argo_client.fetch_orario(studente), {"lunedi": []})
            self.assertEqual(argo_client.fetch_promemoria(studente), [{"testo": "Portare libro"}])
            self.assertEqual(argo_client.fetch_medie(studente), {"generale": "8.5"})

    def test_get_studenti_parsing(self):
        """Verifica il parsing della variabile d'ambiente STUDENTI."""
        raw_json = '[{"nome": "Mario", "codice_scuola": "SG1", "username": "u1"}, {"nome": "SenzaScuola", "username": "u2"}]'
        with patch.dict(os.environ, {"STUDENTI": raw_json}):
            studenti = argo_client.get_studenti()
            self.assertEqual(len(studenti), 1)
            self.assertEqual(studenti[0]["nome"], "Mario")


if __name__ == "__main__":
    unittest.main()
