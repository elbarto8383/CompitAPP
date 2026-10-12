"""
Test di integrazione unitaria per NuvolaConnector in CompitAPP.
Esecuzione completamente offline senza accesso alla rete.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "compitapp"))

from connectors import BaseConnector, NuvolaConnector, get_connector
import argo_client
from nuvola_api.models import (
    Alunno,
    Compito,
    VotoDettaglio,
    Assenza,
    Nota,
    EventoClasse,
    OraLezione,
    ArgomentoLezione,
    FrazioneTemporale,
    MateriaVoti,
)


class TestNuvolaConnector(unittest.TestCase):
    def setUp(self):
        self.studente = {
            "nome": "Luca Rossi",
            "registro": "nuvola",
            "username": "mario.rossi",
            "password": "Password123!",
            "alunno_id": 12345
        }
        self.connector = NuvolaConnector(self.studente)

    def test_inheritance_and_factory(self):
        self.assertIsInstance(self.connector, BaseConnector)
        conn = get_connector(self.studente)
        self.assertIsInstance(conn, NuvolaConnector)

    def test_get_studenti_supports_nuvola_without_codice_scuola(self):
        env_studenti = (
            '[{"nome": "Luca", "registro": "nuvola", "username": "l.rossi"},'
            ' {"nome": "Anna", "registro": "argo", "codice_scuola": "SG1", "username": "a.verdi"},'
            ' {"nome": "InvalidoArgo", "registro": "argo", "username": "inv"}]'
        )
        with patch.dict(os.environ, {"STUDENTI": env_studenti}):
            studenti = argo_client.get_studenti()
            self.assertEqual(len(studenti), 2)
            nomi = [s["nome"] for s in studenti]
            self.assertIn("Luca", nomi)
            self.assertIn("Anna", nomi)
            self.assertNotIn("InvalidoArgo", nomi)

    @patch.object(NuvolaConnector, "get_client")
    def test_fetch_compiti(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.get_compiti.return_value = [
            Compito(
                docente="Prof. Bianchi",
                materia="Italiano",
                data_assegnazione="2026-10-10",
                data_consegna="2026-10-15",
                descrizione="Esercizi pagina 100",
                classe="3B"
            )
        ]

        risultato = self.connector.fetch_compiti()
        self.assertIsInstance(risultato, dict)
        self.assertTrue(len(risultato) > 0)
        for data_iso, payload in risultato.items():
            self.assertIn("materie", payload)
            self.assertIn("compiti", payload)
            self.assertIn("Italiano", payload["materie"])
            self.assertIn("Prof. Bianchi: Esercizi pagina 100", payload["compiti"])

    @patch.object(NuvolaConnector, "get_client")
    def test_fetch_voti(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.get_tutti_voti.return_value = [
            VotoDettaglio(
                data="2026-10-05T00:00:00+02:00",
                docente="Prof. Verdi",
                tipologia="Scritto",
                valutazione="8",
                valutazione_matematica="8.00",
                fa_media=True,
                peso="100%",
                descrizione="Verifica equazioni",
                nome_materia="Matematica",
                id_materia=10,
                id_frazione_temporale=1
            )
        ]

        voti = self.connector.fetch_voti()
        self.assertEqual(len(voti), 1)
        self.assertEqual(voti[0]["data"], "2026-10-05")
        self.assertEqual(voti[0]["materia"], "Matematica")
        self.assertEqual(voti[0]["voto"], "8")
        self.assertEqual(voti[0]["descrizione"], "Verifica equazioni")

    @patch.object(NuvolaConnector, "get_client")
    def test_fetch_assenze(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.get_assenze.return_value = [
            Assenza(
                id=1,
                data="2026-10-03T00:00:00+02:00",
                turno="TURNO MATTINO",
                tipo="RITARDO",
                giustificata=True,
                giustificabile=False,
                ora="08:20"
            )
        ]

        assenze = self.connector.fetch_assenze()
        self.assertEqual(len(assenze), 1)
        self.assertEqual(assenze[0]["data"], "2026-10-03")
        self.assertEqual(assenze[0]["tipo"], "R")
        self.assertTrue(assenze[0]["giustificata"])

    @patch.object(NuvolaConnector, "get_client")
    def test_fetch_medie(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.get_frazioni_temporali.return_value = [
            FrazioneTemporale(id=1, nome="1° Quadrimestre", corrente=True)
        ]
        mock_client.get_voti_materie.return_value = [
            MateriaVoti(id=101, materia="Italiano", conteggio_voti=2, media="7.50"),
            MateriaVoti(id=102, materia="Matematica", conteggio_voti=2, media="8.50"),
        ]

        medie = self.connector.fetch_medie()
        self.assertIsNotNone(medie)
        self.assertEqual(medie["generale"], "8.00")
        self.assertEqual(medie["materie"]["Italiano"], "7.50")
        self.assertEqual(medie["materie"]["Matematica"], "8.50")


if __name__ == "__main__":
    unittest.main()
