import os
import json
from flask import Flask, render_template, jsonify, request
from datetime import date, timedelta
from models import init_db, get_db
from argo_client import get_studenti

def load_config():
    config_path = '/data/options.json'
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                cfg = json.load(f)
            os.environ['TELEGRAM_TOKEN']      = str(cfg.get('telegram_token', ''))
            # Costruisce telegram_chat_ids dai campi individuali
            ids = []
            g1 = str(cfg.get('genitore1_chat_id', '')).strip()
            g2 = str(cfg.get('genitore2_chat_id', '')).strip()
            if g1: ids.append(g1)
            if g2: ids.append(g2)
            # Fallback al vecchio campo telegram_chat_ids se presente
            if not ids:
                old_ids = str(cfg.get('telegram_chat_ids', '')).strip()
                if old_ids: ids = [x.strip() for x in old_ids.replace('\n',',').split(',') if x.strip()]
            os.environ['TELEGRAM_CHAT_IDS']   = ','.join(ids)
            os.environ['GENITORE1_NOME']      = str(cfg.get('genitore1_nome', 'Genitore 1'))
            os.environ['GENITORE1_CHAT_ID']   = g1
            os.environ['GENITORE2_NOME']      = str(cfg.get('genitore2_nome', 'Genitore 2'))
            os.environ['GENITORE2_CHAT_ID']   = g2
            os.environ['STUDENTE_NOME']       = str(cfg.get('studente_nome', 'Studente'))
            os.environ['STUDENTE_CHAT_ID']    = str(cfg.get('studente_chat_id', '')).strip()
            os.environ['SOGLIA_VOTO']         = str(cfg.get('soglia_voto_alert', 7))
            os.environ['ORARIO_REMINDER']     = str(cfg.get('orario_reminder_sera', '20:00'))
            os.environ['POLLING_MINUTI']      = str(cfg.get('polling_intervallo_minuti', 30))
            os.environ['STUDENTI']            = json.dumps(cfg.get('studenti', []))
            os.environ['ANNO_SCOLASTICO']     = str(cfg.get('anno_scolastico', '2025/2026'))
            print(f"[CONFIG] ✅ Token: {os.environ['TELEGRAM_TOKEN'][:15]}...")
            print(f"[CONFIG] Chat IDs: {os.environ['TELEGRAM_CHAT_IDS']}")
            print(f"[CONFIG] Studente Chat ID: {os.environ['STUDENTE_CHAT_ID']}")
        except Exception as e:
            print(f"[CONFIG] Errore: {e}")

load_config()

from scheduler import avvia_scheduler
from bot import avvia_bot

app = Flask(__name__)

def _maschera_token(token):
    """Mostra solo i primi 10 caratteri del token"""
    if not token:
        return ''
    if ':' in token:
        parts = token.split(':')
        return parts[0] + ':' + '*' * len(parts[1])
    return token[:6] + '*' * (len(token) - 6)

def _sel(studenti):
    return request.args.get('studente', studenti[0]['nome'] if studenti else '')

def _media(voti):
    valori = []
    for v in voti:
        try:
            valori.append(float(str(v['voto']).replace(',','.')))
        except Exception:
            pass
    return round(sum(valori)/len(valori), 1) if valori else None

@app.route('/')
def index():
    studenti = get_studenti()
    sel = _sel(studenti)
    oggi = date.today().strftime('%Y-%m-%d')
    domani = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    conn = get_db()
    compiti_oggi   = conn.execute('SELECT * FROM compiti WHERE studente=? AND data=? ORDER BY materia', (sel, oggi)).fetchall()
    compiti_domani = conn.execute('SELECT * FROM compiti WHERE studente=? AND data=? ORDER BY materia', (sel, domani)).fetchall()
    prossimi       = conn.execute('SELECT * FROM compiti WHERE studente=? AND data>? ORDER BY data,materia LIMIT 30', (sel, domani)).fetchall()
    ultimi_voti    = conn.execute('SELECT * FROM voti WHERE studente=? ORDER BY data DESC, id DESC LIMIT 5', (sel,)).fetchall()
    tutti_voti     = conn.execute('SELECT voto FROM voti WHERE studente=?', (sel,)).fetchall()
    bacheca        = conn.execute('SELECT * FROM bacheca WHERE studente=? ORDER BY data DESC LIMIT 3', (sel,)).fetchall()
    promemoria     = conn.execute('SELECT * FROM promemoria WHERE studente=? AND data>=? ORDER BY data', (sel, oggi)).fetchall()
    assenze_tot    = conn.execute("SELECT COUNT(*) as n FROM assenze WHERE studente=? AND tipo='A'", (sel,)).fetchone()['n']
    conn.close()
    return render_template('index.html',
        studenti=studenti, studente_sel=sel,
        compiti_oggi=compiti_oggi, compiti_domani=compiti_domani,
        prossimi=prossimi, ultimi_voti=ultimi_voti,
        bacheca=bacheca, promemoria=promemoria, assenze_mese=assenze_tot,
        media=_media(tutti_voti), oggi=oggi, domani=domani,
        soglia_voto=float(os.environ.get('SOGLIA_VOTO', 7))
    )

@app.route('/calendario')
def calendario():
    studenti = get_studenti()
    sel = _sel(studenti)
    da = (date.today() - timedelta(days=60)).strftime('%Y-%m-%d')
    a  = (date.today() + timedelta(days=30)).strftime('%Y-%m-%d')
    conn = get_db()
    compiti = conn.execute('SELECT * FROM compiti WHERE studente=? AND data BETWEEN ? AND ? ORDER BY data,materia', (sel, da, a)).fetchall()
    conn.close()
    return render_template('calendario.html', compiti=compiti, studenti=studenti,
        studente_sel=sel, oggi=date.today().strftime('%Y-%m-%d'))

@app.route('/voti')
def voti():
    studenti = get_studenti()
    sel = _sel(studenti)
    conn = get_db()
    tutti_voti = conn.execute('SELECT * FROM voti WHERE studente=? ORDER BY data DESC', (sel,)).fetchall()
    conn.close()
    medie = {}
    per_materia = {}
    for v in tutti_voti:
        try:
            per_materia.setdefault(v['materia'], []).append(float(str(v['voto']).replace(',','.')))
        except Exception:
            pass
    for m, vals in per_materia.items():
        medie[m] = round(sum(vals)/len(vals), 1)
    return render_template('voti.html', voti=tutti_voti, medie=medie,
        soglia=float(os.environ.get('SOGLIA_VOTO', 7)),
        studenti=studenti, studente_sel=sel)

@app.route('/bacheca')
def bacheca():
    studenti = get_studenti()
    sel = _sel(studenti)
    conn = get_db()
    msgs = conn.execute('SELECT * FROM bacheca WHERE studente=? ORDER BY data DESC', (sel,)).fetchall()
    conn.close()
    return render_template('bacheca.html', messaggi=msgs, studenti=studenti, studente_sel=sel)

@app.route('/assenze')
def assenze():
    studenti = get_studenti()
    sel = _sel(studenti)
    conn = get_db()
    assenze_list = conn.execute('SELECT * FROM assenze WHERE studente=? ORDER BY data DESC', (sel,)).fetchall()
    stats = {
        'assenze': conn.execute("SELECT COUNT(*) as n FROM assenze WHERE studente=? AND tipo='A'", (sel,)).fetchone()['n'],
        'ritardi': conn.execute("SELECT COUNT(*) as n FROM assenze WHERE studente=? AND tipo='R'", (sel,)).fetchone()['n'],
        'uscite':  conn.execute("SELECT COUNT(*) as n FROM assenze WHERE studente=? AND tipo='U'", (sel,)).fetchone()['n'],
    }
    conn.close()
    return render_template('assenze.html', assenze=assenze_list, stats=stats,
        studenti=studenti, studente_sel=sel)

@app.route('/argomenti')
def argomenti():
    studenti = get_studenti()
    sel = _sel(studenti)
    da = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
    conn = get_db()
    args = conn.execute('SELECT * FROM argomenti WHERE studente=? AND data>=? ORDER BY data DESC, materia', (sel, da)).fetchall()
    conn.close()
    return render_template('argomenti.html', argomenti=args, studenti=studenti, studente_sel=sel)

@app.route('/orario')
def orario():
    studenti = get_studenti()
    sel = _sel(studenti)
    giorno_oggi = date.today().weekday() + 1
    if giorno_oggi > 5:
        giorno_oggi = 0
    return render_template('orario.html', giorno_oggi=giorno_oggi,
        anno_scolastico=os.environ.get('ANNO_SCOLASTICO','2025/2026'),
        studenti=studenti, studente_sel=sel)

@app.route('/configurazione')
def configurazione():
    studenti = get_studenti()
    sel = _sel(studenti)
    
    # Parsing chat_ids
    raw = os.environ.get('TELEGRAM_CHAT_IDS','')
    ids = [x.strip() for x in raw.replace('\n',',').split(',') if x.strip()]
    studente_chat = os.environ.get('STUDENTE_CHAT_ID','').strip()
    
    # Trova credenziali studente selezionato
    cred = next((s for s in studenti if s['nome'] == sel), {})
    
    cfg = {
        'connesso': len(studenti) > 0 and bool(cred.get('codice_scuola')),
        'username': cred.get('username',''),
        'codice_scuola': cred.get('codice_scuola',''),
        'genitore1_nome': os.environ.get('GENITORE1_NOME', 'Genitore 1'),
        'genitore1': os.environ.get('GENITORE1_CHAT_ID', ''),
        'genitore2_nome': os.environ.get('GENITORE2_NOME', 'Genitore 2'),
        'genitore2': os.environ.get('GENITORE2_CHAT_ID', ''),
        'studente_nome': os.environ.get('STUDENTE_NOME', 'Studente'),
        'studente_chat_id': studente_chat,
        'totale_destinatari': len(ids) + (1 if studente_chat else 0),
        'soglia_voto': os.environ.get('SOGLIA_VOTO', 7),
        'orario_reminder': os.environ.get('ORARIO_REMINDER', '20:00'),
        'polling_minuti': os.environ.get('POLLING_MINUTI', 30),
        'token_masked': _maschera_token(os.environ.get('TELEGRAM_TOKEN', '')),
    }
    return render_template('configurazione.html', config=cfg, studenti=studenti, studente_sel=sel)

# ── API ──────────────────────────────────────────────────────────────────────

@app.route('/api/sync', methods=['POST'])
def api_sync():
    from scheduler import sync_tutto
    sync_tutto()
    return jsonify({'ok': True})

@app.route('/api/test-connessione', methods=['POST'])
def api_test_connessione():
    try:
        from argo_client import fetch_compiti
        studenti = get_studenti()
        if not studenti:
            return jsonify({'ok': False, 'errore': 'Nessuno studente configurato'})
        compiti = fetch_compiti(studenti[0])
        return jsonify({'ok': True, 'n_compiti': len(compiti)})
    except Exception as e:
        return jsonify({'ok': False, 'errore': str(e)})

@app.route('/api/test-telegram', methods=['POST'])
def api_test_telegram():
    from notifier import send_telegram_to
    data = request.get_json()
    chat_id = data.get('chat_id','')
    nome = data.get('nome','utente')
    if not chat_id:
        return jsonify({'ok': False})
    ok = send_telegram_to(chat_id, f"🧪 <b>CompitAPP — Test notifica</b>\n✅ Tutto funziona!\nMessaggio per <b>{nome}</b>.")
    return jsonify({'ok': ok})

@app.route('/api/test-broadcast', methods=['POST'])
def api_test_broadcast():
    from notifier import send_telegram
    ok = send_telegram("🧪 <b>CompitAPP — Test broadcast</b>\n✅ Tutti i destinatari ricevono correttamente!")
    ids = [x.strip() for x in os.environ.get('TELEGRAM_CHAT_IDS','').replace('\n',',').split(',') if x.strip()]
    studente_chat = os.environ.get('STUDENTE_CHAT_ID','').strip()
    n = len(ids) + (1 if studente_chat else 0)
    return jsonify({'ok': ok, 'n': n})

@app.route('/api/reset-db', methods=['POST'])
def api_reset_db():
    try:
        conn = get_db()
        for tabella in ['compiti','voti','assenze','note_disciplinari','bacheca','argomenti','promemoria']:
            conn.execute(f'DELETE FROM {tabella}')
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'errore': str(e)})

@app.route('/api/stats')
def api_stats():
    sel = request.args.get('studente', '')
    oggi = date.today().strftime('%Y-%m-%d')
    domani = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    conn = get_db()
    n_oggi     = conn.execute('SELECT COUNT(*) as n FROM compiti WHERE studente=? AND data=?', (sel, oggi)).fetchone()['n']
    n_domani   = conn.execute('SELECT COUNT(*) as n FROM compiti WHERE studente=? AND data=?', (sel, domani)).fetchone()['n']
    tot_comp   = conn.execute('SELECT COUNT(*) as n FROM compiti WHERE studente=?', (sel,)).fetchone()['n']
    tot_voti   = conn.execute('SELECT COUNT(*) as n FROM voti WHERE studente=?', (sel,)).fetchone()['n']
    tot_ass    = conn.execute('SELECT COUNT(*) as n FROM assenze WHERE studente=?', (sel,)).fetchone()['n']
    tot_bach   = conn.execute('SELECT COUNT(*) as n FROM bacheca WHERE studente=?', (sel,)).fetchone()['n']
    ultimo     = conn.execute("SELECT creato_il FROM compiti WHERE studente=? ORDER BY id DESC LIMIT 1", (sel,)).fetchone()
    conn.close()
    return jsonify({
        'compiti_oggi': n_oggi, 'compiti_domani': n_domani,
        'totale_compiti': tot_comp, 'totale_voti': tot_voti,
        'totale_assenze': tot_ass, 'totale_bacheca': tot_bach,
        'ultimo_sync': ultimo['creato_il'] if ultimo else 'Mai'
    })

if __name__ == '__main__':
    init_db()
    avvia_bot()
    avvia_scheduler()
    app.run(host='0.0.0.0', port=5002, debug=False)
