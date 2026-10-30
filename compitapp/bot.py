import os
import threading
import requests
import time
from datetime import date, timedelta

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')

GIORNI_ITA = {
    0: 'lunedi', 1: 'martedi', 2: 'mercoledi', 3: 'giovedi', 4: 'venerdi', 5: 'sabato', 6: None
}
GIORNI_NOME = {
    'lunedi': '☀️ Lunedì', 'martedi': '🌤️ Martedì', 'mercoledi': '🌈 Mercoledì',
    'giovedi': '⚡ Giovedì', 'venerdi': '🎉 Venerdì', 'sabato': '🎈 Sabato'
}
EMOJI_MATERIE = {
    'Italiano': '📝', 'Storia': '📜', 'Tecnologia': '💻', 'Inglese': '🇬🇧',
    'Religione': '✝️', 'Scienze Motorie': '⚽', 'Matematica': '🔢',
    'Arte e Immagine': '🎨', 'Scienze': '🔬', 'Geografia': '🌍', 'Musica': '🎵',
}
MESI_ITA = {
    1:'gennaio',2:'febbraio',3:'marzo',4:'aprile',5:'maggio',6:'giugno',
    7:'luglio',8:'agosto',9:'settembre',10:'ottobre',11:'novembre',12:'dicembre'
}

def data_ita(d):
    from datetime import datetime
    if isinstance(d, str):
        d = datetime.strptime(d, '%Y-%m-%d').date()
    giorni = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica']
    return f"{giorni[d.weekday()]} {d.day} {MESI_ITA[d.month]}"

def handle_update(update):
    try:
        message = update.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        text = (message.get('text', '') or '').strip()
        first_name = message.get('chat', {}).get('first_name', 'utente')
        if not chat_id or not text:
            return

        cmd = text.split()[0].lower().split('@')[0]
        args = text.split()[1:] if len(text.split()) > 1 else []

        if cmd == '/start':
            _cmd_start(chat_id, first_name)
        elif cmd == '/chatid':
            _cmd_chatid(chat_id)
        elif cmd == '/resoconto':
            _cmd_resoconto(chat_id)
        elif cmd == '/orario':
            _cmd_orario(chat_id, args)
        elif cmd == '/voti':
            _cmd_voti(chat_id)
        elif cmd == '/help':
            _cmd_help(chat_id)

    except Exception as e:
        print(f"[BOT] Errore handle_update: {e}")

def _cmd_start(chat_id, first_name):
    send_message(chat_id,
        f"👋 Ciao <b>{first_name}</b>!\n\n"
        f"Benvenuto in <b>CompitAPP</b> 📚\n"
        f"Il tuo assistente per compiti e voti scolastici.\n\n"
        f"🔢 Il tuo <b>Chat ID</b> è:\n<code>{chat_id}</code>\n\n"
        f"💡 Comunicalo all'amministratore per ricevere le notifiche.\n\n"
        f"Digita /help per vedere tutti i comandi disponibili."
    )

def _cmd_chatid(chat_id):
    send_message(chat_id,
        f"🔢 Il tuo <b>Chat ID</b> è:\n\n<code>{chat_id}</code>"
    )

def _cmd_help(chat_id):
    send_message(chat_id,
        f"📚 <b>CompitAPP — Comandi</b>\n\n"
        f"/start — Benvenuto e Chat ID\n"
        f"/chatid — Mostra il tuo Chat ID\n"
        f"/resoconto — Riepilogo compiti + voti\n"
        f"/orario — Orario di oggi\n"
        f"/orario lunedi — Orario di un giorno specifico\n"
        f"/voti — Ultimi voti e medie\n"
        f"/help — Questo messaggio\n\n"
        f"<i>Le notifiche arrivano automaticamente quando il prof inserisce compiti o voti su DiDUP.</i>"
    )

def _studenti_bot():
    """Nomi degli studenti configurati (come salvati nel database)."""
    try:
        from argo_client import get_studenti
        nomi = [st.get('nome', 'default') for st in get_studenti()]
    except Exception:
        nomi = []
    return nomi or ['default']

def _cmd_resoconto(chat_id):
    try:
        from models import get_db
        conn = get_db()
        nomi = _studenti_bot()
        for nome in nomi:
            send_message(chat_id, _testo_resoconto(conn, nome, mostra_nome=len(nomi) > 1))
        conn.close()
    except Exception as e:
        print(f"[BOT] Errore resoconto: {e}")
        send_message(chat_id, "❌ Errore nel recupero del resoconto.")

def _testo_resoconto(conn, nome, mostra_nome=False):
    oggi = date.today().strftime('%Y-%m-%d')
    domani = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    fra_7_giorni = (date.today() + timedelta(days=7)).strftime('%Y-%m-%d')

    c_oggi = conn.execute(
        'SELECT materia, testo FROM compiti WHERE studente=? AND data=? ORDER BY materia', (nome, oggi)).fetchall()
    c_domani = conn.execute(
        'SELECT materia, testo FROM compiti WHERE studente=? AND data=? ORDER BY materia', (nome, domani)).fetchall()
    c_prossimi = conn.execute(
        'SELECT data, materia, testo FROM compiti WHERE studente=? AND data > ? AND data <= ? ORDER BY data, materia',
        (nome, domani, fra_7_giorni)).fetchall()
    ultimi_voti = conn.execute(
        'SELECT materia, voto, data FROM voti WHERE studente=? ORDER BY data DESC, id DESC LIMIT 3', (nome,)).fetchall()

    msg = f"📋 <b>Resoconto CompitAPP</b>\n<i>{data_ita(date.today())}</i>\n"
    if mostra_nome:
        msg += f"🎒 <b>{nome}</b>\n"
    msg += "\n"

    msg += f"📖 <b>Compiti per oggi</b>\n"
    if c_oggi:
        for c in c_oggi:
            emoji = EMOJI_MATERIE.get(c['materia'], '📚')
            msg += f"{emoji} <b>{c['materia']}</b>: {c['testo'][:80]}{'...' if len(c['testo'])>80 else ''}\n"
    else:
        msg += "✅ Nessun compito!\n"

    msg += f"\n🌙 <b>Compiti per domani</b>\n"
    if c_domani:
        for c in c_domani:
            emoji = EMOJI_MATERIE.get(c['materia'], '📚')
            msg += f"{emoji} <b>{c['materia']}</b>: {c['testo'][:80]}{'...' if len(c['testo'])>80 else ''}\n"
    else:
        msg += "✅ Nessun compito!\n"

    if c_prossimi:
        msg += f"\n📅 <b>Prossimi giorni</b>\n"
        data_prec = ''
        for c in c_prossimi:
            if c['data'] != data_prec:
                msg += f"\n<i>{data_ita(c['data'])}</i>\n"
                data_prec = c['data']
            emoji = EMOJI_MATERIE.get(c['materia'], '📚')
            msg += f"{emoji} <b>{c['materia']}</b>: {c['testo'][:60]}{'...' if len(c['testo'])>60 else ''}\n"

    if ultimi_voti:
        msg += f"\n⭐ <b>Ultimi voti</b>\n"
        for v in ultimi_voti:
            try:
                vn = float(str(v['voto']).replace(',','.'))
                soglia = float(os.environ.get('SOGLIA_VOTO', 7))
                em = '🟢' if vn >= soglia else ('🟡' if vn >= soglia-1 else '🔴')
            except Exception:
                em = '📊'
            msg += f"{em} <b>{v['materia']}</b>: {v['voto']} <i>({v['data']})</i>\n"
    return msg

def _cmd_orario(chat_id, args):
    from argo_client import get_studenti
    from models import get_db
    from orario_utils import emoji_materia

    # Determina il giorno richiesto
    if args:
        alias = {
            'lun': 'lunedi', 'lunedi': 'lunedi', 'lunedì': 'lunedi',
            'mar': 'martedi', 'martedi': 'martedi', 'martedì': 'martedi',
            'mer': 'mercoledi', 'mercoledi': 'mercoledi', 'mercoledì': 'mercoledi',
            'gio': 'giovedi', 'giovedi': 'giovedi', 'giovedì': 'giovedi',
            'ven': 'venerdi', 'venerdi': 'venerdi', 'venerdì': 'venerdi',
            'sab': 'sabato', 'sabato': 'sabato',
        }
        giorno_key = alias.get(args[0].lower())
        if not giorno_key:
            send_message(chat_id, "❓ Giorno non riconosciuto.\nUsa: /orario lunedi (o mar, mer, gio, ven, sab)")
            return
        e_oggi = False
    else:
        giorno_key = GIORNI_ITA.get(date.today().weekday())
        e_oggi = True
        if not giorno_key:
            send_message(chat_id, "📅 Oggi è weekend — nessuna lezione!\n\nUsa /orario lunedi per vedere l'orario di un giorno specifico.")
            return

    giorno_idx = list(GIORNI_NOME.keys()).index(giorno_key)
    nome_giorno = GIORNI_NOME.get(giorno_key, giorno_key.capitalize())

    try:
        studenti = get_studenti() or [{'nome': 'default'}]
        conn = get_db()
        blocchi = []
        for st in studenti:
            nome = st.get('nome', 'default')
            ore = conn.execute(
                'SELECT ora, materia, docente FROM orario WHERE studente=? AND giorno=? ORDER BY ora',
                (nome, giorno_idx)
            ).fetchall()
            ha_orario = conn.execute('SELECT 1 FROM orario WHERE studente=? LIMIT 1', (nome,)).fetchone()
            blocchi.append((nome, ore, ha_orario))
        conn.close()
    except Exception as e:
        print(f"[BOT] Errore orario: {e}")
        send_message(chat_id, "❌ Errore nel recupero dell'orario.")
        return

    if giorno_key == 'sabato' and e_oggi and not any(ore for _, ore, _ in blocchi):
        send_message(chat_id, "📅 Oggi è weekend — nessuna lezione!\n\nUsa /orario lunedi per vedere l'orario di un giorno specifico.")
        return

    for nome, ore, ha_orario in blocchi:
        msg = f"🗓️ <b>Orario {nome_giorno}</b>"
        if e_oggi:
            msg += " <i>(oggi)</i>"
        msg += "\n\n"
        if not ha_orario:
            msg += "📭 Orario non ancora disponibile: viene ricostruito dalle lezioni del registro.\n"
        elif not ore:
            msg += "Nessuna lezione in questo giorno.\n"
        else:
            for r in ore:
                msg += f"{r['ora']}ª {emoji_materia(r['materia'])} <b>{r['materia']}</b>\n"
                if r['docente']:
                    msg += f"   <i>👤 {r['docente']}</i>\n"
        msg += f"\n<i>📚 {nome}</i>"
        send_message(chat_id, msg)

def _cmd_voti(chat_id):
    try:
        from models import get_db
        conn = get_db()
        nomi = _studenti_bot()
        testi = []
        for nome in nomi:
            voti = conn.execute(
                'SELECT materia, voto, data FROM voti WHERE studente=? ORDER BY data DESC, id DESC LIMIT 15', (nome,)
            ).fetchall()
            testi.append((nome, voti))
        conn.close()

        soglia = float(os.environ.get('SOGLIA_VOTO', 7))
        for nome, voti in testi:
            titolo = f"⭐ <b>Voti di {nome}</b>" if nome != 'default' else "⭐ <b>Voti</b>"
            if not voti:
                send_message(chat_id, f"{titolo}\n\n📊 Nessun voto registrato.")
                continue

            per_materia = {}
            for v in voti:
                try:
                    per_materia.setdefault(v['materia'], []).append(float(str(v['voto']).replace(',','.')))
                except Exception:
                    pass

            msg = f"{titolo}\n\n<b>Media per materia:</b>\n"
            for mat, vals in sorted(per_materia.items()):
                media = round(sum(vals)/len(vals), 1)
                em = '🟢' if media >= soglia else ('🟡' if media >= soglia-1 else '🔴')
                msg += f"{em} <b>{mat}</b>: {media}\n"

            msg += "\n<b>Ultimi voti:</b>\n"
            for v in voti[:8]:
                try:
                    vn = float(str(v['voto']).replace(',','.'))
                    em = '🟢' if vn >= soglia else ('🟡' if vn >= soglia-1 else '🔴')
                except Exception:
                    em = '📊'
                msg += f"{em} {v['materia']}: <b>{v['voto']}</b> <i>({v['data']})</i>\n"
            send_message(chat_id, msg)

    except Exception as e:
        print(f"[BOT] Errore voti: {e}")
        send_message(chat_id, "❌ Errore nel recupero dei voti.")

def send_message(chat_id, testo):
    if not TELEGRAM_TOKEN:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={'chat_id': chat_id, 'text': testo, 'parse_mode': 'HTML'},
            timeout=10
        )
    except Exception as e:
        print(f"[BOT] Errore send: {e}")

def set_comandi_bot():
    """Imposta i comandi del bot automaticamente all'avvio"""
    if not TELEGRAM_TOKEN:
        return
    comandi = [
        {"command": "start",     "description": "Benvenuto e ottieni il tuo Chat ID"},
        {"command": "chatid",    "description": "Mostra il tuo Chat ID"},
        {"command": "resoconto", "description": "Riepilogo compiti e voti di oggi"},
        {"command": "orario",    "description": "Orario di oggi (o /orario lunedi)"},
        {"command": "voti",      "description": "Ultimi voti e medie per materia"},
        {"command": "help",      "description": "Mostra tutti i comandi"},
    ]
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setMyCommands",
            json={"commands": comandi},
            timeout=10
        )
        if resp.status_code == 200:
            print("[BOT] ✅ Comandi impostati automaticamente")
        else:
            print(f"[BOT] ⚠️ Errore impostazione comandi: {resp.text}")
    except Exception as e:
        print(f"[BOT] Errore setMyCommands: {e}")

def polling_loop():
    if not TELEGRAM_TOKEN:
        print("[BOT] Token mancante — polling non avviato")
        return
    offset = 0
    print("[BOT] Polling avviato ✅")
    while True:
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params={'offset': offset, 'timeout': 30},
                timeout=35
            )
            if resp.status_code == 200:
                for update in resp.json().get('result', []):
                    offset = update['update_id'] + 1
                    handle_update(update)
        except Exception as e:
            print(f"[BOT] Errore polling: {e}")
            time.sleep(5)

def avvia_bot():
    if not TELEGRAM_TOKEN:
        print("[BOT] Token non configurato")
        return
    mode = os.environ.get('TELEGRAM_RICEZIONE', 'polling')
    if mode == 'home_assistant':
        from ha_telegram_bridge import run_bridge
        threading.Thread(target=run_bridge, args=(handle_update,), daemon=True).start()
        print('[BOT] Ricezione tramite Home Assistant; polling Telegram disattivato', flush=True)
        return
    if mode != 'polling':
        print('[BOT] Modalita ricezione non valida; polling non avviato', flush=True)
        return
    set_comandi_bot()
    threading.Thread(target=polling_loop, daemon=True).start()
    print("[BOT] Thread avviato ✅")
