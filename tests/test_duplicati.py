"""
Test offline: un testo lungo non deve essere salvato (e notificato) di nuovo a ogni sincronizzazione.
Regressione della issue #8: il controllo dei duplicati confrontava i primi 200 caratteri mentre
nel database se ne salvavano fino a 500, quindi un promemoria piu' lungo di 200 caratteri non
risultava mai «gia' presente» e veniva notificato a ogni ciclo.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "compitapp")))

import models
import scheduler

STUDENTE = {"nome": "Luigi", "codice_scuola": "SG1", "username": "u", "password": "p"}
LUNGO = "Verifica di Promessi Sposi: " + "introduzione al romanzo, " * 12   # circa 300 caratteri
MOLTO_LUNGO = "Esercizi da svolgere: " + "pagina 12 numeri 1-10, " * 40       # circa 900 caratteri


class BaseDb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "t.db")
        self.p_db = patch.object(models, "DB_PATH", self.path)
        self.p_db.start()
        models.init_db()
        self.p_st = patch.object(scheduler, "get_studenti", return_value=[STUDENTE])
        self.p_pr = patch.object(scheduler, "_prepara", return_value=(7, False))
        self.p_st.start(); self.p_pr.start()

    def tearDown(self):
        patch.stopall()
        self.tmp.cleanup()

    def righe(self, tabella):
        c = sqlite3.connect(self.path)
        try:
            return c.execute(f"SELECT COUNT(*) FROM {tabella}").fetchone()[0]
        finally:
            c.close()


class TestNoDuplicatiConTestiLunghi(BaseDb):

    def test_promemoria_lungo_notificato_una_sola_volta(self):
        self.assertGreater(len(LUNGO), 200)
        dati = [{"data": "2026-10-14", "testo": LUNGO, "docente": "Prof"}]
        with patch.object(scheduler, "fetch_promemoria", return_value=dati), \
                patch.object(scheduler, "notifica_promemoria") as notifica:
            for _ in range(4):
                scheduler.sync_promemoria()
        self.assertEqual(self.righe("promemoria"), 1)
        self.assertEqual(notifica.call_count, 1)

    def test_nota_lunga_notificata_una_sola_volta(self):
        dati = [{"data": "2026-10-14", "testo": LUNGO, "docente": "Prof"}]
        with patch.object(scheduler, "fetch_note", return_value=dati), \
                patch.object(scheduler, "notifica_nota") as notifica:
            for _ in range(4):
                scheduler.sync_note()
        self.assertEqual(self.righe("note_disciplinari"), 1)
        self.assertEqual(notifica.call_count, 1)

    def test_argomento_lungo_salvato_una_sola_volta(self):
        dati = [{"data": "2026-10-14", "materia": "Italiano", "argomento": LUNGO, "attivita": ""}]
        with patch.object(scheduler, "fetch_argomenti", return_value=dati):
            for _ in range(4):
                scheduler.sync_argomenti()
        self.assertEqual(self.righe("argomenti"), 1)

    def test_compito_molto_lungo_notificato_una_sola_volta(self):
        raw = {"2026-10-20": {"materie": ["Matematica"], "compiti": [MOLTO_LUNGO]}}
        with patch.object(scheduler, "fetch_compiti", return_value=raw), \
                patch.object(scheduler, "notifica_nuovi_compiti") as notifica:
            for _ in range(4):
                scheduler.sync_compiti()
        self.assertEqual(self.righe("compiti"), 1)
        self.assertLessEqual(notifica.call_count, 1)

    def test_bacheca_titolo_lungo_senza_uid_una_sola_volta(self):
        titolo = "Circolare " + "x" * 300
        dati = [{"data": "2026-10-14", "titolo": titolo, "testo": "t", "mittente": "Dirigente", "uid": ""}]
        with patch.object(scheduler, "fetch_bacheca", return_value=dati), \
                patch.object(scheduler, "notifica_bacheca") as notifica:
            for _ in range(4):
                scheduler.sync_bacheca()
        self.assertEqual(self.righe("bacheca"), 1)
        self.assertLessEqual(notifica.call_count, 1)

    def test_testo_breve_resta_invariato(self):
        dati = [{"data": "2026-10-14", "testo": "Portare il libro", "docente": "Prof"}]
        with patch.object(scheduler, "fetch_promemoria", return_value=dati), \
                patch.object(scheduler, "notifica_promemoria") as notifica:
            for _ in range(3):
                scheduler.sync_promemoria()
        self.assertEqual(self.righe("promemoria"), 1)
        self.assertEqual(notifica.call_count, 1)


class TestPuliziaDuplicatiEsistenti(BaseDb):

    def _duplica(self):
        c = sqlite3.connect(self.path)
        for _ in range(5):
            c.execute("INSERT INTO promemoria (studente,data,testo,docente,notificato) VALUES (?,?,?,?,1)",
                      ("Luigi", "2026-10-14", LUNGO[:500], "Prof"))
            c.execute("INSERT INTO note_disciplinari (studente,data,docente,testo,notificato) VALUES (?,?,?,?,1)",
                      ("Luigi", "2026-10-14", "Prof", LUNGO))
            c.execute("INSERT INTO argomenti (studente,data,materia,argomento,attivita) VALUES (?,?,?,?,?)",
                      ("Luigi", "2026-10-14", "Italiano", LUNGO[:500], ""))
            c.execute("INSERT INTO compiti (studente,data,materia,testo) VALUES (?,?,?,?)",
                      ("Luigi", "2026-10-20", "Matematica", MOLTO_LUNGO[:1000]))
        # voci distinte, che devono restare
        c.execute("INSERT INTO promemoria (studente,data,testo,docente,notificato) VALUES (?,?,?,?,1)",
                  ("Luigi", "2026-10-15", "altro promemoria", "Prof"))
        c.execute("INSERT INTO promemoria (studente,data,testo,docente,notificato) VALUES (?,?,?,?,1)",
                  ("Altro", "2026-10-14", LUNGO[:500], "Prof"))
        c.commit(); c.close()

    def _come_db_vecchio(self):
        """Un database creato prima della 2.1.2 non ha il segno della pulizia."""
        c = sqlite3.connect(self.path)
        c.execute("DELETE FROM meta WHERE chiave='pulizia_duplicati:2.1.2'")
        c.commit(); c.close()

    def test_init_db_rimuove_i_duplicati_una_volta(self):
        self._duplica()
        self._come_db_vecchio()
        self.assertEqual(self.righe("promemoria"), 7)
        models.init_db()
        self.assertEqual(self.righe("promemoria"), 3)        # 1 lungo + 1 distinto + 1 di un altro studente
        self.assertEqual(self.righe("note_disciplinari"), 1)
        self.assertEqual(self.righe("argomenti"), 1)
        self.assertEqual(self.righe("compiti"), 1)

    def test_pulizia_e_una_tantum(self):
        self._duplica()
        self._come_db_vecchio()
        models.init_db()
        self.assertEqual(self.righe("note_disciplinari"), 1)
        self._duplica()          # nuovi doppioni dopo la pulizia: non vengono toccati di nascosto
        models.init_db()
        self.assertGreater(self.righe("note_disciplinari"), 1)

    def test_tiene_la_riga_piu_vecchia(self):
        self._duplica()
        self._come_db_vecchio()
        c = sqlite3.connect(self.path)
        primo = c.execute("SELECT MIN(id) FROM note_disciplinari").fetchone()[0]
        c.close()
        models.init_db()
        c = sqlite3.connect(self.path)
        rimasto = c.execute("SELECT id FROM note_disciplinari").fetchone()[0]
        c.close()
        self.assertEqual(rimasto, primo)


if __name__ == "__main__":
    unittest.main()
