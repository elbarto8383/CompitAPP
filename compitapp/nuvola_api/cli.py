"""
Interfaccia a riga di comando (CLI) per l'interazione con le API di Nuvola.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, List

from .client import NuvolaClient
from .exceptions import NuvolaError


def format_table(headers: List[str], rows: List[List[Any]]) -> str:
    """Formatta una matrice di dati in una tabella testuale monospazio per il terminale."""
    if not rows:
        return "Nessun dato disponibile."
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))

    header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    sep_line = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    row_lines = [
        " | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(row))
        for row in rows
    ]
    return f"{header_line}\n{sep_line}\n" + "\n".join(row_lines)


def main() -> None:
    """Punto di ingresso principale della CLI nuvola-cli."""
    parser = argparse.ArgumentParser(
        prog="nuvola-cli",
        description="Interfaccia a riga di comando per le API del registro elettronico Nuvola (Madisoft S.p.A.)"
    )
    parser.add_argument(
        "--session-file",
        default="nuvola_session.json",
        help="Percorso del file JSON per la persistenza della sessione (default: nuvola_session.json)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emette l'output grezzo strutturato in formato JSON"
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando operativo da eseguire")

    # Comando: login
    login_p = subparsers.add_parser("login", help="Effettua l'autenticazione iniziale e memorizza i token")
    login_p.add_argument("-u", "--username", help="Nome utente dell'account Nuvola")

    # Comando: refresh
    subparsers.add_parser("refresh", help="Rinnova manualmente il token di accesso tramite refresh token")

    # Comando: alunni
    subparsers.add_parser("alunni", help="Elenca gli studenti associati al profilo genitore/tutore")

    # Comando: compiti
    compiti_p = subparsers.add_parser("compiti", help="Interroga i compiti per casa assegnati per una data")
    compiti_p.add_argument("--alunno-id", type=int, required=True, help="Identificativo numerico dell'alunno")
    compiti_p.add_argument("--data", default=datetime.now().strftime("%d-%m-%Y"), help="Data nel formato DD-MM-YYYY (default: data odierna)")

    # Comando: orario
    orario_p = subparsers.add_parser("orario", help="Mostra l'orario delle lezioni e gli argomenti trattati")
    orario_p.add_argument("--alunno-id", type=int, required=True, help="Identificativo numerico dell'alunno")
    orario_p.add_argument("--data", default=datetime.now().strftime("%d-%m-%Y"), help="Data nel formato DD-MM-YYYY (default: data odierna)")

    # Comando: voti
    voti_p = subparsers.add_parser("voti", help="Elenca lo storico delle valutazioni dell'alunno")
    voti_p.add_argument("--alunno-id", type=int, required=True, help="Identificativo numerico dell'alunno")

    # Comando: assenze
    assenze_p = subparsers.add_parser("assenze", help="Elenca assenze, ritardi e uscite anticipate")
    assenze_p.add_argument("--alunno-id", type=int, required=True, help="Identificativo numerico dell'alunno")

    # Comando: eventi
    eventi_p = subparsers.add_parser("eventi", help="Elenca le verifiche programmate e gli eventi di classe")
    eventi_p.add_argument("--alunno-id", type=int, required=True, help="Identificativo numerico dell'alunno")

    # Comando: pagamenti
    pagamenti_p = subparsers.add_parser("pagamenti", help="Elenca i contributi e i pagamenti PagoPA")
    pagamenti_p.add_argument("--alunno-id", type=int, required=True, help="Identificativo numerico dell'alunno")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    username = getattr(args, "username", None) or os.getenv("NUVOLA_USERNAME")
    password = os.getenv("NUVOLA_PASSWORD")

    client = NuvolaClient(
        username=username,
        password=password,
        session_file=args.session_file
    )

    try:
        if args.command == "login":
            if not username or not password:
                import getpass
                if not username:
                    username = input("Username Nuvola: ").strip()
                if not password:
                    password = getpass.getpass("Password Nuvola: ").strip()
            client.login(username=username, password=password)
            print(f"[SUCCESSO] Autenticazione completata. Sessione salvata in: {args.session_file}")
            return

        if args.command == "refresh":
            ok = client.refresh_token()
            if ok:
                print("[SUCCESSO] Token di accesso rinnovato correttamente.")
            else:
                print("[ERRORE] Rinnovo del token fallito. Eseguire nuovamente il comando di login.", file=sys.stderr)
                sys.exit(1)
            return

        if args.command == "alunni":
            if args.json:
                print(json.dumps(client.get_alunni_raw(), indent=2, ensure_ascii=False))
            else:
                alunni = client.get_alunni()
                rows = [[a.id, a.nome_completo, a.classe, a.scuola] for a in alunni]
                print(format_table(["ID", "Nome Completo", "Classe", "Scuola"], rows))
            return

        if args.command == "compiti":
            if args.json:
                print(json.dumps(client.get_compiti_raw(args.alunno_id, args.data), indent=2, ensure_ascii=False))
            else:
                compiti = client.get_compiti(args.alunno_id, args.data)
                rows = [[c.materia, c.docente, c.descrizione.replace("\n", " ")[:60]] for c in compiti]
                print(f"Compiti per il {args.data}:")
                print(format_table(["Materia", "Docente", "Descrizione"], rows))
            return

        if args.command == "orario":
            if args.json:
                print(json.dumps(client.get_argomenti_lezione_raw(args.alunno_id, args.data), indent=2, ensure_ascii=False))
            else:
                ore = client.get_argomenti_lezione(args.alunno_id, args.data)
                rows = []
                for o in ore:
                    for arg in o.argomenti:
                        rows.append([f"Ora {o.numero_ora} ({o.inizio_ora}-{o.fine_ora})", arg.materia, arg.docente, arg.nome_argomento])
                print(f"Orario del {args.data}:")
                print(format_table(["Orario", "Materia", "Docente", "Argomento"], rows))
            return

        if args.command == "voti":
            voti = client.get_tutti_voti(args.alunno_id)
            if args.json:
                print(json.dumps([v.raw for v in voti], indent=2, ensure_ascii=False))
            else:
                rows = [[v.data[:10], v.nome_materia, v.valutazione, v.tipologia, v.docente] for v in voti]
                print(format_table(["Data", "Materia", "Voto", "Tipo", "Docente"], rows))
            return

        if args.command == "assenze":
            assenze = client.get_assenze(args.alunno_id)
            if args.json:
                print(json.dumps([a.raw for a in assenze], indent=2, ensure_ascii=False))
            else:
                rows = [[a.data[:10], a.tipo, "Si" if a.giustificata else "No", a.ora or "-"] for a in assenze]
                print(format_table(["Data", "Tipo", "Giustificata", "Ora"], rows))
            return

        if args.command == "eventi":
            eventi = client.get_eventi_classe(args.alunno_id)
            if args.json:
                print(json.dumps([e.raw for e in eventi], indent=2, ensure_ascii=False))
            else:
                rows = [[e.data_inizio[:10], e.tipo, e.nome, e.docente] for e in eventi]
                print(format_table(["Data", "Tipo", "Oggetto", "Docente"], rows))
            return

        if args.command == "pagamenti":
            pagamenti = client.get_pagamenti(args.alunno_id)
            if args.json:
                print(json.dumps([p.raw for p in pagamenti], indent=2, ensure_ascii=False))
            else:
                rows = [[p.tassa[:35], p.importo, p.stato_pagamento, p.data_scadenza or "-"] for p in pagamenti]
                print(format_table(["Descrizione", "Importo", "Stato", "Scadenza"], rows))
            return

    except NuvolaError as e:
        print(f"[ERRORE NUVOLA] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERRORE CRITICO] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
