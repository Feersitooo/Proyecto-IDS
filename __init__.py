import os
import sqlite3
from datetime import timedelta
from pathlib import Path
import click
from dotenv import load_dotenv
from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.exceptions import SecurityError
from . import db, data
from .errors import DomainError
from .timeutils import display, due_notice


def create_app(test_config=None):
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / '.env')
    app = Flask(__name__, instance_path=str(root / 'instance'))
    database_path = Path(os.getenv('DATABASE_PATH', 'instance/biblioteca.sqlite3')).expanduser()
    if not database_path.is_absolute():
        database_path = root / database_path
    app.config.from_mapping(
        APP_MODE=os.getenv('APP_MODE','local'),
        SECRET_KEY=os.getenv('SECRET_KEY'), DATABASE=str(database_path),
        DUE_SOON_HOURS=int(os.getenv('DUE_SOON_HOURS', '48')),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE', '0') == '1',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        SESSION_REFRESH_EACH_REQUEST=False, MAX_CONTENT_LENGTH=64 * 1024,
        WTF_CSRF_TIME_LIMIT=7200,
        TRUSTED_HOSTS=[h.strip() for h in os.getenv('TRUSTED_HOSTS','').split(',') if h.strip()] or None,
    )
    if test_config:
        app.config.update(test_config)
    key = app.config['SECRET_KEY']
    if not key or len(key) < 32 or key.startswith('REEMPLAZAR'):
        raise RuntimeError('Configura SECRET_KEY en .env con una clave aleatoria de al menos 32 caracteres. Consulta README.md.')
    if not 1 <= app.config['DUE_SOON_HOURS'] <= 720:
        raise RuntimeError('DUE_SOON_HOURS debe estar entre 1 y 720 horas.')
    if app.config['APP_MODE'] not in ('local','production'):
        raise RuntimeError('APP_MODE debe ser local o production.')
    if app.config['APP_MODE']=='local' and not app.config['TRUSTED_HOSTS']:
        app.config['TRUSTED_HOSTS']=['localhost','127.0.0.1']
    if app.config['APP_MODE']=='production':
        if not app.config['SESSION_COOKIE_SECURE'] or not app.config['TRUSTED_HOSTS']:
            raise RuntimeError('Publicación: configura COOKIE_SECURE=1 y TRUSTED_HOSTS con tu dominio HTTPS.')
        if app.debug or app.testing or os.getenv('FLASK_DEBUG','0').lower() not in ('0','false',''):
            raise RuntimeError('No se permite DEBUG ni TESTING en producción.')
    CSRFProtect(app)
    app.teardown_appcontext(db.close_db)
    from .auth import bp as auth_bp, load_user
    from .catalog import bp as catalog_bp
    from .views import bp as views_bp
    from .favorites import bp as favorites_bp
    from .cloud_accounts import bp as cloud_accounts_bp
    app.register_blueprint(cloud_accounts_bp)
    app.before_request(load_user)
    for blueprint in (auth_bp, catalog_bp, views_bp, favorites_bp):
        app.register_blueprint(blueprint)
    from .commands import register_commands
    register_commands(app)
    app.jinja_env.filters['localdate'] = display
    app.jinja_env.globals.update(due_notice=due_notice)

    @app.context_processor
    def notification_count():
        from flask import g
        if g.get('user') and g.user['role']=='alumno':
            return {'unread_count':len(data.notifications(g.user['id'],True))}
        return {'unread_count':0}

    @app.get('/healthz')
    def health():
        ready = data.metadata('schema_version')=='2'
        return {'status':'ok' if ready else 'unavailable'}, (200 if ready else 503)

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        response.headers['Cache-Control'] = 'no-store'
        if app.config['SESSION_COOKIE_SECURE']:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.errorhandler(DomainError)
    def domain_error(error):
        return render_template('error.html', code=error.status, message=error.message), error.status

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template('error.html', code=400, message='El formulario expiró o no es válido. Vuelve a abrir la página e inténtalo nuevamente.'), 400

    @app.errorhandler(SecurityError)
    def invalid_host(error):
        # Un host inválido no dispone de rutas con las que renderizar la plantilla.
        return 'Dirección de servidor no permitida.', 400, {'Content-Type':'text/plain; charset=utf-8'}

    @app.errorhandler(sqlite3.IntegrityError)
    def integrity_error(error):
        app.logger.warning('Operación detenida por integridad: %s', error)
        return render_template('error.html', code=409, message='La operación entra en conflicto con el estado actual o con un identificador existente. Actualiza la página y revisa los datos.'), 409

    @app.errorhandler(sqlite3.OperationalError)
    def database_busy(error):
        app.logger.error('Error SQLite: %s', error)
        return render_template('error.html', code=503, message='La base de datos no está disponible en este momento. Inténtalo nuevamente o revisa su inicialización.'), 503

    for status in (400,403,404,405,413,500):
        def handler(error, code=status):
            messages = {400:'La solicitud no es válida.',403:'No tienes permiso para acceder a esta página.',404:'No encontramos esa página o registro.',405:'Esta acción requiere el formulario correspondiente.',413:'El formulario es demasiado grande.',500:'No se pudo completar la operación. Revisa el registro del servidor.'}
            return render_template('error.html', code=code, message=messages[code]), code
        app.register_error_handler(status, handler)

    @app.cli.command('init-db')
    def init_command():
        """Crea una base NUEVA con esquema y reglas, sin cuentas ni ejemplos."""
        try:
            db.initialize()
        except FileExistsError:
            raise click.ClickException('La base ya existe: no se modificó. Usa otra DATABASE_PATH para una demo nueva.') from None
        click.echo('Base creada. Carga ejemplos con: python -m flask --app app seed-demo')

    @app.cli.command('seed-demo')
    def seed_command():
        """Carga ejemplos una sola vez y solo en una base vacía."""
        from .seed import seed_demo
        try:
            seed_demo()
        except DomainError as exc:
            raise click.ClickException(exc.message) from exc
        click.echo('Demostración cargada. Credenciales en README.md.')

    @app.cli.command('set-rule')
    @click.option('--user-type', default='pregrado', show_default=True)
    @click.option('--collection', 'collection_id', required=True)
    @click.option('--max-items', type=click.IntRange(1,100), required=True)
    @click.option('--days', type=click.IntRange(1,365), required=True)
    @click.option('--hour', type=click.IntRange(0,23), required=True)
    def set_rule(user_type, collection_id, max_items, days, hour):
        """Actualiza una regla. No cambia vencimientos ya registrados."""
        if not data.rule(user_type, collection_id):
            raise click.ClickException('Combinación no configurada. Añade el tipo/colección mediante una migración revisada.')
        with db.transaction():
            data.change_rule(user_type, collection_id, max_items, days, hour)
            data.audit(None, 'regla_actualizada_cli', 0, f'{user_type}/{collection_id}: {max_items} ejemplares, {days} días, {hour}:00')
        click.echo('Regla actualizada; revisa el panel Reglas.')

    return app
