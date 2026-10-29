"""Empaqueta Flask y genera la primera migración, sin datos de una instalación local."""
import json
import mimetypes
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biblioteca import create_app, db, data
from biblioteca.seed import seed_demo


def prepare():
    package = ROOT / 'python_modules'
    package.mkdir(exist_ok=True)
    shutil.copytree(ROOT / 'biblioteca', package / 'biblioteca', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__'))
    schema = (ROOT / 'biblioteca/schema.sql').read_text() + '\n' + db.migration_sql()
    templates = {str(p.relative_to(ROOT / 'biblioteca/templates')): p.read_text()
                 for p in (ROOT / 'biblioteca/templates').rglob('*.html')}
    static = {p.name: (p.read_text(), mimetypes.guess_type(p.name)[0] or 'text/plain')
              for p in (ROOT / 'biblioteca/static').iterdir() if p.is_file()}
    (package / 'cloud_bundle.py').write_text('SCHEMA = ' + repr(schema) + '\nTEMPLATES = ' + repr(templates) + '\nSTATIC = ' + repr(static) + '\n')

    with tempfile.TemporaryDirectory() as directory:
        app = create_app(dict(SECRET_KEY=secrets.token_hex(32), DATABASE=str(Path(directory)/'initial.sqlite3'), APP_MODE='local'))
        with app.app_context():
            db.initialize()
            seed_demo()
            with db.transaction():
                data.disable_demo_accounts()
                # Las claves conocidas no se incluyen ni siquiera como hash activo.
                data.write("UPDATE users SET password_hash='disabled-until-reset'")
            connection = db.get_db()
            objects = connection.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'").fetchall()
            tables = [row['name'] for row in objects if row['type'] == 'table']
            # D1 mantiene las claves foráneas activas: primero se crean todas
            # las tablas y después se cargan padres antes que hijos.
            statements = [row['sql']+';' for row in objects if row['type']=='table']
            loaded = set()
            while len(loaded) < len(tables):
                ready = [table for table in tables if table not in loaded and
                         {r['table'] for r in connection.execute(f'PRAGMA foreign_key_list("{table}")')} <= loaded]
                if not ready:
                    raise RuntimeError('La migración inicial contiene referencias circulares.')
                for table in ready:
                    for row in connection.execute(f'SELECT * FROM "{table}"'):
                        values = ','.join(connection.execute('SELECT quote(?)',(value,)).fetchone()[0] for value in row)
                        statements.append(f'INSERT INTO "{table}" VALUES({values});')
                    loaded.add(table)
            statements += [row['sql']+';' for row in objects if row['type']!='table']
            dump = '\n'.join(statements)
        dump += '''
CREATE TABLE cloud_revision(id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER NOT NULL);
INSERT INTO cloud_revision VALUES(1,0);
CREATE TRIGGER cloud_revision_guard BEFORE UPDATE ON cloud_revision
WHEN NEW.value != OLD.value + 1 OR NEW.id != OLD.id
BEGIN SELECT RAISE(ABORT,'stale_revision'); END;
CREATE TRIGGER cloud_revision_preserve BEFORE DELETE ON cloud_revision
BEGIN SELECT RAISE(ABORT,'revision_required'); END;
'''
        migrations = ROOT / 'cloudflare/migrations'
        migrations.mkdir(parents=True, exist_ok=True)
        (migrations / '0001_initial.sql').write_text(dump)
    print('Aplicación empaquetada; migración inicial con cuentas de ejemplo desactivadas.')


if __name__ == '__main__':
    prepare()
