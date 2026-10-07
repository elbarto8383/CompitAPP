"""Entry point principale CompitAPP"""
import sys
import os
import json

sys.path.insert(0, '/app')

# Carica configurazione
config_path = '/data/options.json'
if os.path.exists(config_path):
    with open(config_path) as f:
        cfg = json.load(f)
    ids = []
    g1 = str(cfg.get('genitore1_chat_id', '')).strip()
    g2 = str(cfg.get('genitore2_chat_id', '')).strip()
    if g1: ids.append(g1)
    if g2: ids.append(g2)
    if not ids:
        old = str(cfg.get('telegram_chat_ids', '')).strip()
        if old: ids = [x.strip() for x in old.replace('\n',',').split(',') if x.strip()]
    os.environ['TELEGRAM_TOKEN']    = str(cfg.get('telegram_token', ''))
    os.environ['TELEGRAM_CHAT_IDS'] = ','.join(ids)
    os.environ['STUDENTE_CHAT_ID']  = str(cfg.get('studente_chat_id', '')).strip()
    os.environ['GENITORE1_NOME']    = str(cfg.get('genitore1_nome', 'Genitore 1'))
    os.environ['GENITORE1_CHAT_ID'] = g1
    os.environ['GENITORE2_NOME']    = str(cfg.get('genitore2_nome', 'Genitore 2'))
    os.environ['GENITORE2_CHAT_ID'] = g2
    os.environ['STUDENTE_NOME']     = str(cfg.get('studente_nome', 'Studente'))
    os.environ['SOGLIA_VOTO']       = str(cfg.get('soglia_voto_alert', 7))
    os.environ['ORARIO_REMINDER']   = str(cfg.get('orario_reminder_sera', '20:00'))
    os.environ['POLLING_MINUTI']    = str(cfg.get('polling_intervallo_minuti', 30))
    os.environ['REMINDER_MODALITA']      = str(cfg.get('reminder_modalita', 'auto'))
    os.environ['REMINDER_MOSTRA_ORARIO'] = '1' if cfg.get('reminder_mostra_orario', False) else '0'
    os.environ['REMINDER_TESTO_VUOTO']   = str(cfg.get('reminder_testo_vuoto', '') or '')
    os.environ['REMINDER_TESTO_CHIUSURA'] = str(cfg.get('reminder_testo_chiusura', '') or '')
    os.environ['STUDENTI']          = json.dumps(cfg.get('studenti', []))
    os.environ['ANNO_SCOLASTICO']   = str(cfg.get('anno_scolastico', '2025/2026'))
    print(f"[CONFIG] ✅ Token: {os.environ['TELEGRAM_TOKEN'][:15]}...")
    print(f"[CONFIG] Chat IDs: {os.environ['TELEGRAM_CHAT_IDS']}")

def installa_card():
    """Copia la card Lovelace in /config/www/compitapp/ (si vede come /local/compitapp/compitapp-card.js)"""
    import shutil
    sorgente = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'card', 'compitapp-card.js')
    destinazione = '/config/www/compitapp'
    try:
        if not os.path.isdir('/config'):
            return
        os.makedirs(destinazione, exist_ok=True)
        shutil.copyfile(sorgente, os.path.join(destinazione, 'compitapp-card.js'))
        print("[CARD] ✅ Card installata: aggiungi la risorsa /local/compitapp/compitapp-card.js (tipo: modulo JavaScript)")
    except Exception as e:
        print(f"[CARD] Non riesco a installare la card ({e}). Puoi copiarla a mano da GitHub: compitapp/card/compitapp-card.js")

installa_card()

from models import init_db
from bot import avvia_bot
from scheduler import avvia_scheduler
from app import app

# Inizializza PRIMA di avviare Flask
print("[APP] Inizializzazione...")
init_db()
avvia_bot()
avvia_scheduler()
print("[APP] ✅ Pronto!")

if __name__ == '__main__':
    print("[APP] Avvio Flask threaded sulla porta 5002...")
    app.run(host='0.0.0.0', port=5002, debug=False, threaded=True)
