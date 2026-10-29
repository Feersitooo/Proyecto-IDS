import hmac
import re
from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
from .passwords import generate_password_hash
from . import data
from .auth import role_required
from .db import transaction
from .errors import DomainError
from .security import valid_password

bp = Blueprint('cloud_accounts', __name__)


def account_fields():
    email = request.form.get('email', '').strip().lower()
    name = request.form.get('name', '').strip()
    password = request.form.get('password', '')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 254:
        raise DomainError('Ingresa un correo válido.')
    if not 2 <= len(name) <= 100:
        raise DomainError('El nombre debe tener entre 2 y 100 caracteres.')
    if not valid_password(password):
        raise DomainError('Usa una contraseña propia de 12 a 200 caracteres.')
    return email, name, generate_password_hash(password, method='pbkdf2:sha256:600000')


@bp.route('/configurar', methods=['GET', 'POST'])
def setup():
    if not current_app.config.get('CLOUD_D1') or data.deployment_counts()['admins']:
        abort(404)
    if request.method == 'POST':
        expected = current_app.config.get('SETUP_TOKEN', '')
        supplied = request.form.get('setup_token', '')
        if len(expected) < 32 or not hmac.compare_digest(supplied.encode(), expected.encode()):
            abort(403)
        email, name, password_hash = account_fields()
        with transaction():
            if data.deployment_counts()['admins']:
                abort(409)
            ident = data.add_user(email, name, password_hash, role='admin')
            data.audit(ident, 'administrador_inicial_creado', ident)
        flash('Administrador creado. Inicia sesión con tu correo y contraseña.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('cloud_account.html', setup=True)


@bp.route('/admin/cuentas/nueva', methods=['GET', 'POST'])
@role_required('admin')
def create():
    if request.method == 'POST':
        email, name, password_hash = account_fields()
        with transaction():
            ident = data.add_user(email, name, password_hash)
            data.audit(g.user['id'], 'alumno_creado', ident)
        flash('Cuenta de alumno creada. Entrega su contraseña por un medio privado.', 'success')
        return redirect(url_for('views.students'))
    return render_template('cloud_account.html', setup=False)


@bp.post('/admin/cuentas/<int:user_id>/clave')
@role_required('admin')
def reset_password(user_id):
    password = request.form.get('password', '')
    if not valid_password(password):
        raise DomainError('Usa una contraseña nueva de 12 a 200 caracteres.')
    password_hash = generate_password_hash(password, method='pbkdf2:sha256:600000')
    with transaction():
        student = data.user(user_id)
        if not student or student['role'] != 'alumno':
            abort(404)
        data.change_password(user_id, password_hash)
        # Una cuenta de ejemplo solo se habilita después de cambiar su clave pública.
        data.write('UPDATE users SET is_demo=0,account_active=1 WHERE id=?', (user_id,))
        data.audit(g.user['id'], 'clave_alumno_restablecida', user_id)
    flash('Contraseña cambiada y cuenta activa. Se cerraron sus sesiones anteriores.', 'success')
    return redirect(url_for('views.students'))
