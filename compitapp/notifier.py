import os
import json
import html
import requests
from datetime import date, datetime, timedelta
from orario_utils import emoji_materia

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_IDS_RAW = os.environ.get('TELEGRAM_CHAT_IDS', '')
SUPERVISOR_TOKEN = os.environ.get('SUPERVISOR_TOKEN', '')
SOGLIA_VOTO = int(os.environ.get('SOGLIA_VOTO', 7))

GIORNI_ITA = {'Monday':'Lunedì','Tuesday':'Martedì','Wednesday':'Mercoledì',
              'Thursday':'Giovedì','Friday':'Venerdì','Saturday':'Sabato','Sunday':'Domenica'}
MESI_ITA = {1:'gennaio',2:'febbraio',3:'marzo',4:'aprile',5:'maggio',6:'giugno',
            7:'luglio',8:'agosto',9:'settembre',10:'ottobre',11:'novembre',12:'dicembre'}

TIPO_ASSENZA = {'A':'🏠 Assenza','R':'⏰ Ritardo','U':'🚪 Uscita anticipata'}

def get_chat_ids():
    if TELEGRAM_CHAT_IDS_RAW:
        return [x.strip() for x in TELEGRAM_CHAT_IDS_RAW.replace('\n',',').split(',') if x.strip()]
    return []

def _data_ita(d):
    if isinstance(d, str):
        try:
            d = datetime.strptime(d, '%Y-%m-%d').date()
        except Exception:
            return d
    return f"{GIORNI_ITA.get(d.strftime('%A'), d.strftime('%A'))} {d.day} {MESI_ITA[d.month]}"

def send_telegram(messaggio):
    token = TELEGRAM_TOKEN
    chat_ids = get_chat_ids()
    if not token or not chat_ids:
        print("[TELEGRAM] Token o chat_id mancanti")
        return False
    ok = True
    for chat_id in chat_ids:
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={'chat_id': chat_id, 'text': messaggio, 'parse_mode': 'HTML'},
                timeout=10
            )
            print(f"[TELEGRAM] {'✅' if resp.status_code==200 else '❌'} → {chat_id}")
            if resp.status_code != 200:
                ok = False
        except Exception as e:
            print(f"[TELEGRAM] Errore {chat_id}: {e}")
            ok = False
    return ok

def notifica_nuovi_compiti(nome, compiti_nuovi):
    if not compiti_nuovi:
        return
    for data, info in sorted(compiti_nuovi.items()):
        msg = f"📚 <b>{nome} — Compiti per {_data_ita(data)}</b>\n\n"
        for materia, testo in zip(info['materie'], info['compiti']):
            msg += f"📖 <b>{materia}</b>\n{testo}\n\n"
        send_telegram_compiti(msg.strip(), nome)

def notifica_nuovo_voto(nome, materia, voto, descrizione=''):
    try:
        voto_num = float(str(voto).replace(',','.'))
        if voto_num < SOGLIA_VOTO:
            emoji, avviso = "🔴", f"\n⚠️ <i>Sotto soglia ({SOGLIA_VOTO})!</i>"
        elif voto_num >= 9:
            emoji, avviso = "🌟", "\n🎉 <i>Ottimo risultato!</i>"
        elif voto_num >= 7:
            emoji, avviso = "🟢", ""
        else:
            emoji, avviso = "🟡", ""
    except Exception:
        emoji, avviso = "📊", ""
    msg = f"{emoji} <b>{nome} — Nuovo voto!</b>\n\n📖 <b>{materia}</b>\n📊 Voto: <b>{voto}</b>{avviso}"
    if descrizione:
        msg += f"\n💬 {descrizione}"
    send_telegram(msg)

def notifica_assenza(nome, data, tipo):
    label = TIPO_ASSENZA.get(tipo, f'📋 {tipo}')
    send_telegram(f"{label}\n👤 <b>{nome}</b>\n📅 {_data_ita(data)}")

def notifica_nota(nome, data, docente, testo):
    msg = f"⚠️ <b>Nota disciplinare — {nome}</b>\n\n"
    msg += f"📅 {_data_ita(data)}\n"
    if docente:
        msg += f"👤 {docente}\n"
    msg += f"\n<i>{testo[:300]}</i>"
    send_telegram(msg)

def notifica_bacheca(nome, titolo, testo, mittente=''):
    msg = f"📢 <b>Comunicazione scuola</b>\n\n"
    msg += f"📌 <b>{titolo}</b>\n"
    if mittente:
        msg += f"👤 {mittente}\n"
    if testo:
        msg += f"\n<i>{testo[:400]}</i>"
    send_telegram_compiti(msg, nome)

def notifica_promemoria(nome, data, docente, testo):
    msg = f"📋 <b>Promemoria — {nome}</b>\n\n"
    msg += f"📅 {_data_ita(data)}\n"
    if docente:
        msg += f"👤 {docente}\n"
    msg += f"\n{testo[:300]}"
    send_telegram_compiti(msg, nome)

def _opt_bool(chiave, default):
    v = os.environ.get(chiave)
    if v is None or v == '':
        return default
    return str(v).strip().lower() in ('1', 'true', 'yes', 'si', 'sì', 'on')

def _opt_testo(chiave, default):
    v = os.environ.get(chiave, '').strip()
    return html.escape(v, quote=False) if v else default

def reminder_compiti_domani(nome, compiti_domani, domani_scuola=True, orario_domani=None):
    """Riepilogo serale dei compiti per domani.

    Personalizzabile da configurazione (variabili d'ambiente impostate in wsgi.py):
      REMINDER_MODALITA        auto (default) | sempre | solo_con_compiti
      REMINDER_MOSTRA_ORARIO   1/0 — aggiunge l'orario di domani
      REMINDER_TESTO_VUOTO     frase quando non ci sono compiti
      REMINDER_TESTO_CHIUSURA  frase finale quando ci sono compiti
    In modalità auto il messaggio "nessun compito" non parte se domani non è giorno di scuola
    (es. sabato per chi non ha lezioni il sabato); con compiti assegnati parte sempre.
    """
    domani = date.today() + timedelta(days=1)
    modalita = os.environ.get('REMINDER_MODALITA', 'auto').strip().lower() or 'auto'
    ha_compiti = bool(compiti_domani and compiti_domani.get('materie'))

    if not ha_compiti:
        if modalita == 'solo_con_compiti':
            print(f"[REMINDER] {nome}: nessun compito per domani, riepilogo non inviato (modalità solo_con_compiti)")
            return
        if modalita == 'auto' and not domani_scuola:
            print(f"[REMINDER] {nome}: domani ({_data_ita(domani)}) non è giorno di scuola e non ci sono compiti, riepilogo non inviato")
            return

    testo_vuoto = _opt_testo('REMINDER_TESTO_VUOTO', '🎉 Buona serata!')
    testo_chiusura = _opt_testo('REMINDER_TESTO_CHIUSURA', '📌 <i>Buona fortuna! 💪</i>')

    if not ha_compiti:
        msg = f"✅ <b>{nome}</b> — Nessun compito per domani!\n{testo_vuoto}"
    else:
        msg = f"🌙 <b>{nome} — Compiti per {_data_ita(domani)}</b>\n\n"
        for materia, testo in zip(compiti_domani['materie'], compiti_domani['compiti']):
            msg += f"📖 <b>{materia}</b>\n{testo}\n\n"
        msg += testo_chiusura

    if orario_domani and _opt_bool('REMINDER_MOSTRA_ORARIO', False):
        msg += f"\n\n🗓️ <b>Orario di {_data_ita(domani).split()[0].lower()}</b>\n"
        for ora, materia in orario_domani:
            msg += f"{ora}ª {emoji_materia(materia)} {materia}\n"
    send_telegram_compiti(msg.strip(), nome)

def sync_sensori_ha(nome, stats):
    if not SUPERVISOR_TOKEN:
        return
    headers = {'Authorization': f'Bearer {SUPERVISOR_TOKEN}', 'Content-Type': 'application/json'}
    slug = nome.lower().replace(' ','_')
    base = 'http://supervisor/core/api/states'
    det = stats.get('dettagli') or {}
    sensori = {
        f'sensor.compitapp_{slug}_compiti_oggi':    {'state': stats.get('compiti_oggi',0), 'attributes': {'friendly_name': f'CompitAPP {nome} - Compiti oggi', 'icon': 'mdi:book-open', 'unit_of_measurement': 'compiti', 'elenco': det.get('compiti_oggi', [])}},
        f'sensor.compitapp_{slug}_compiti_domani':  {'state': stats.get('compiti_domani',0), 'attributes': {'friendly_name': f'CompitAPP {nome} - Compiti domani', 'icon': 'mdi:book-clock', 'unit_of_measurement': 'compiti', 'elenco': det.get('compiti_domani', [])}},
        f'sensor.compitapp_{slug}_assenze':         {'state': stats.get('assenze_totali',0), 'attributes': {'friendly_name': f'CompitAPP {nome} - Assenze', 'icon': 'mdi:account-off', 'elenco': det.get('assenze', [])}},
        f'sensor.compitapp_{slug}_bacheca':         {'state': stats.get('bacheca_non_lette',0), 'attributes': {'friendly_name': f'CompitAPP {nome} - Bacheca', 'icon': 'mdi:bulletin-board', 'elenco': det.get('bacheca', [])}},
        f'sensor.compitapp_{slug}_ultimo_voto':     {'state': stats.get('ultimo_voto','N/D'), 'attributes': {'friendly_name': f'CompitAPP {nome} - Ultimo voto', 'materia': stats.get('ultima_materia',''), 'icon': 'mdi:star', 'elenco': det.get('voti', [])}},
        f'sensor.compitapp_{slug}_media_voti':      {'state': stats.get('media_voti','N/D'), 'attributes': {'friendly_name': f'CompitAPP {nome} - Media voti', 'icon': 'mdi:chart-line', 'medie': det.get('medie', [])}},
    }
    for entity_id, payload in sensori.items():
        try:
            requests.post(f'{base}/{entity_id}', json=payload, headers=headers, timeout=5)
        except Exception as e:
            print(f"[HA] Errore {entity_id}: {e}")

def send_telegram_to(chat_id, messaggio):
    """Invia a un singolo chat_id specifico"""
    token = TELEGRAM_TOKEN
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={'chat_id': chat_id, 'text': messaggio, 'parse_mode': 'HTML'},
            timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[TELEGRAM] Errore send_to {chat_id}: {e}")
        return False

def _studenti_config():
    try:
        return [s for s in json.loads(os.environ.get('STUDENTI', '[]') or '[]') if s.get('nome')]
    except Exception:
        return []

def get_studente_chat_id(nome=None):
    """Chat ID dello studente (non riceve i voti).

    Ogni studente può avere il proprio `chat_id` nella lista `studenti`.
    Il vecchio campo `studente_chat_id` vale solo se c'è un unico studente.
    """
    studenti = _studenti_config()
    if nome:
        for s in studenti:
            if s.get('nome') == nome:
                cid = str(s.get('chat_id', '') or '').strip()
                if cid:
                    return cid
    legacy = os.environ.get('STUDENTE_CHAT_ID', '').strip()
    if legacy and len(studenti) <= 1:
        return legacy
    return ''

def send_telegram_compiti(messaggio, nome=None):
    """Invia ai genitori + allo studente indicato (se ha un chat_id)"""
    send_telegram(messaggio)
    studente_id = get_studente_chat_id(nome)
    if studente_id and studente_id not in get_chat_ids():
        send_telegram_to(studente_id, messaggio)

def send_telegram_voti(messaggio):
    """Invia SOLO ai genitori — NON allo studente"""
    send_telegram(messaggio)
    # Lo studente_chat_id viene deliberatamente escluso
