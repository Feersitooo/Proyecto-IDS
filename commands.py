import re
from pathlib import Path
import click
from werkzeug.security import generate_password_hash
from . import data, db
from .security import valid_password, deployment_problems


def ask_password():
    password = click.prompt('Contraseña nueva (12 a 200 caracteres)', hide_input=True, confirmation_prompt=True)
    if not valid_password(password):
        raise click.ClickException('Usa entre 12 y 200 caracteres y una contraseña distinta de la demo.')
    return generate_password_hash(password)


def register_commands(app):
    @app.cli.command('upgrade-db')
    def upgrade_db():
        """Actualiza la versión 1 conservando sus registros y una copia previa."""
        saved = db.upgrade()
        click.echo(f'Base actualizada. Respaldo previo: {saved}' if saved else 'Base en versión 2; no se modificó.')

    @app.cli.command('backup-db')
    @click.argument('destination', type=click.Path(path_type=Path))
    def backup_db(destination):
        """Respaldo coherente de SQLite; no sobrescribe archivos."""
        try:
            click.echo(f'Respaldo guardado: {db.backup(destination)}')
        except FileExistsError:
            raise click.ClickException('El archivo de destino ya existe.') from None

    @app.cli.command('create-user')
    @click.option('--email', required=True)
    @click.option('--name', required=True)
    @click.option('--role', type=click.Choice(['admin','alumno']), default='alumno')
    def create_user(email, name, role):
        email, name = email.strip().lower(), name.strip()
        if len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or email.endswith('@demo.test'):
            raise click.ClickException('Usa un correo válido fuera del dominio reservado demo.test.')
        if not 2<=len(name)<=120:
            raise click.ClickException('El nombre debe tener entre 2 y 120 caracteres.')
        if data.user_by_email(email):
            raise click.ClickException('Ese correo ya está registrado.')
        password_hash = ask_password()
        with db.transaction():
            ident = data.add_user(email,name,password_hash,role=role)
            data.audit(None,'cuenta_creada_cli',ident,role)
        click.echo('Cuenta creada. La contraseña no se guarda en texto plano.')

    @app.cli.command('set-password')
    @click.option('--email', required=True)
    def set_password(email):
        user = data.user_by_email(email.strip().lower())
        if not user:
            raise click.ClickException('Cuenta no encontrada.')
        password_hash = ask_password()
        with db.transaction():
            data.change_password(user['id'],password_hash)
            data.audit(None,'clave_cambiada_cli',user['id'])
        click.echo('Contraseña actualizada. Las sesiones anteriores quedan revocadas.')

    @app.cli.command('disable-demo-accounts')
    def disable_demo():
        with db.transaction():
            count = data.disable_demo_accounts()
            data.audit(None,'cuentas_demo_desactivadas_cli',0,str(count))
        click.echo(f'{count} cuentas desactivadas. Su historial se conserva.')

    @app.cli.command('check-deployment')
    def check_deployment():
        problems = deployment_problems()
        if app.config['APP_MODE']!='production':
            problems.append('Configura APP_MODE=production para publicar.')
        if problems:
            raise click.ClickException(' '.join(problems))
        click.echo('Configuración básica de publicación comprobada. No sustituye una auditoría de seguridad.')
