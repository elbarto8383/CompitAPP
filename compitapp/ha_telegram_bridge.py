"""Receive CompitAPP commands from HA; never poll Telegram in this mode."""
import json
import os
import time

import requests

COMMANDS = frozenset({'/voti', '/orario', '/resoconto'})
STREAM_URL = 'http://supervisor/core/api/stream'


def parent_chat_ids():
    """Only parents: upstream grade commands return data for all students."""
    result = set()
    for value in os.environ.get('TELEGRAM_CHAT_IDS', '').split(','):
        try:
            result.add(int(value.strip()))
        except ValueError:
            pass
    return result


def to_update(event, allowed):
    if not isinstance(event, dict) or event.get('event_type') != 'telegram_command':
        return None
    data = event.get('data')
    if not isinstance(data, dict):
        return None
    try:
        if not isinstance(data.get('chat_id'), (int, str)) or isinstance(data.get('chat_id'), bool):
            return None
        chat_id = int(data['chat_id'])
    except (KeyError, ValueError, TypeError, OverflowError):
        return None
    if chat_id not in allowed:
        return None
    command = data.get('command')
    if not isinstance(command, str) or command.lower() not in COMMANDS:
        return None
    args = data.get('args', [])
    if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
        return None
    return {'message': {'chat': {'id': chat_id, 'first_name': 'utente'},
                        'text': ' '.join([command.lower(), *args])}}


def sse_events(lines):
    """Decode UTF-8 SSE frames, ignoring heartbeats and malformed frames."""
    fields = []
    for raw in lines:
        line = raw.decode('utf-8') if isinstance(raw, bytes) else raw
        if line == '':
            payload = '\n'.join(fields)
            fields.clear()
            if payload and payload != 'ping':
                try:
                    event = json.loads(payload)
                except (ValueError, TypeError):
                    continue
                if isinstance(event, dict):
                    yield event
        elif line.startswith('data:'):
            fields.append(line[5:].removeprefix(' '))


def run_bridge(handle_update):
    allowed = parent_chat_ids()
    if not allowed:
        print('[BOT HA] Nessuna chat genitore configurata; ricezione disabilitata', flush=True)
        return
    # No fallback to Telegram: HA must remain the only getUpdates consumer.
    while True:
        token = os.environ.get('SUPERVISOR_TOKEN', '')
        if not token:
            print('[BOT HA] Autenticazione Supervisor assente; riprovo tra 30 secondi', flush=True)
            time.sleep(30)
            continue
        try:
            with requests.get(
                STREAM_URL,
                headers={'Authorization': 'Bearer ' + token,
                         'Accept': 'text/event-stream'},
                params={'restrict': 'telegram_command'},
                stream=True, timeout=(10, 90), allow_redirects=False,
            ) as response:
                response.raise_for_status()
                # Supervisor may omit Content-Type on a proxied SSE response.
                # The fixed endpoint and SSE/event validation remain mandatory.
                media_type = response.headers.get('Content-Type', '').partition(';')[0].strip().lower()
                if response.status_code != 200 or media_type not in ('', 'text/event-stream'):
                    raise ValueError('Unexpected stream response')
                print('[BOT HA] Connesso: voti, orario, resoconto', flush=True)
                for event in sse_events(response.iter_lines(chunk_size=1)):
                    update = to_update(event, allowed)
                    if update is not None:
                        try:
                            handle_update(update)
                        except Exception:
                            print('[BOT HA] Comando non completato; nessun reinvio automatico', flush=True)
        except (requests.RequestException, ValueError, UnicodeError):
            # Never print exceptions/headers: they may contain credentials.
            print('[BOT HA] Connessione interrotta o rifiutata; riprovo tra 5 secondi', flush=True)
        time.sleep(5)
