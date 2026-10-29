from functools import wraps
from flask import Blueprint, g, session, request, render_template, redirect, url_for, abort, current_app
from .passwords import check_password_hash
from . import data
from .db import transaction
from .security import reserve_login_attempt

bp = Blueprint('auth', __name__)
DUMMY_HASH = 'pbkdf2:sha256:600000$Y0e08khq9TPjSuA4$827ceab9f5f2490593a6649d3f9fcbfa853654c8971193e2a8ea163c30534c64'


def load_user():
    ident = session.get('user_id')
    g.user = data.user(ident) if ident else None
    if g.user and (not g.user['account_active'] or session.get('session_version') != g.user['session_version']
                   or (current_app.config['APP_MODE']=='production' and g.user['is_demo'])):
        session.clear()
        g.user = None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        return view(*args, **kwargs)
    return wrapped


def role_required(role):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user['role'] != role:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


@bp.route('/ingresar', methods=['GET','POST'])
def login():
    if g.user:
        return redirect(url_for('views.home'))
    error = None
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()[:254]
        password = request.form.get('password','')
        attempt_key = reserve_login_attempt(email)
        if attempt_key is None:
            return render_template('login.html',error='Demasiados intentos. Espera 15 minutos antes de volver a intentar.'), 429, {'Retry-After':'900'}
        user = data.user_by_email(email)
        valid = len(password) <= 200 and check_password_hash(user['password_hash'] if user else DUMMY_HASH, password)
        if not user or not valid or not user['account_active'] or (current_app.config['APP_MODE']=='production' and user['is_demo']):
            error = 'Correo o contraseña incorrectos, o cuenta inactiva.'
        else:
            with transaction():
                # Releer evita iniciar una sesión con una clave revocada en paralelo.
                fresh = data.user(user['id'])
                if not fresh['account_active'] or fresh['session_version'] != user['session_version']:
                    return render_template('login.html',error='Correo o contraseña incorrectos, o cuenta inactiva.'), 400
                data.clear_account_attempts(attempt_key)
            session.clear()
            session['user_id'] = user['id']
            session['session_version'] = user['session_version']
            session.permanent = True
            return redirect(url_for('views.home'))
    return render_template('login.html', error=error), (400 if error else 200)


@bp.post('/salir')
@login_required
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
