"""Entry point per Gunicorn — inizializza tutto prima di servire"""
from app import app, init_db, avvia_bot, avvia_scheduler

# Inizializza al caricamento del modulo (eseguito da Gunicorn all'avvio)
init_db()
avvia_bot()
avvia_scheduler()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=False)
