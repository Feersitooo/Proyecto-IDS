import hashlib
import hmac
from datetime import timedelta
from flask import current_app, request
from . import data
from .db import transaction
from .timeutils import now_utc, stamp


def login_key(value):
    secret = current_app.config['SECRET_KEY'].encode()
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()


def reserve_login_attempt(email):
    # No confiamos en X-Forwarded-For enviado por el visitante.
    client_key = login_key(request.remote_addr or 'unknown')
    account_key = login_key(email)
    since = stamp(now_utc() - timedelta(minutes=15))
    with transaction():
        counts = data.login_counts(account_key, client_key, since)
        if counts['account'] >= 5 or counts['client'] >= 50:
            return None
        data.add_login_attempt(account_key, client_key)
    return account_key


def valid_password(password):
    return 12 <= len(password) <= 200 and password != 'DemoUCN2026!'


def deployment_problems():
    counts = data.deployment_counts()
    problems = []
    if counts['demo_active']:
        problems.append('Desactiva las cuentas demo con disable-demo-accounts.')
    if not counts['admins']:
        problems.append('Crea una cuenta de administrador propia con create-user.')
    return problems
