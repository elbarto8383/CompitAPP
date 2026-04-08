"""Entry point per Gunicorn"""
from app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=False)
