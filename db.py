"""Conexión por contexto Flask y transacciones de escritura serializadas."""
import sqlite3
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from flask import current_app, g


def normalize(value):
    text = unicodedata.normalize('NFKD', value or '').casefold()
    return ''.join(c for c in text if not unicodedata.combining(c))


def get_db():
    if 'db' not in g and current_app.config.get('CLOUD_D1'):
        from flask import request
        from .cloud_db import SnapshotConnection, CloudflareBackend
        from cloud_bundle import SCHEMA
        g.db = SnapshotConnection(CloudflareBackend(request.environ['workers.env'].DB), SCHEMA)
    if 'db' not in g:
        path = Path(current_app.config['DATABASE'])
        if not path.exists():
            raise RuntimeError('Base no inicializada. Ejecuta: python -m flask --app app init-db')
        conn = sqlite3.connect(path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA busy_timeout = 10000')
        conn.create_function('normalize', 1, normalize, deterministic=True)
        g.db = conn
    return g.db


def close_db(error=None):
    conn = g.pop('db', None)
    if conn is not None:
        conn.close()


@contextmanager
def transaction():
    from . import data
    conn = get_db()
    conn.execute('BEGIN IMMEDIATE')
    try:
        before = data.available_book_ids()
        yield conn
        # El aviso y la operación se confirman juntos; un rollback revierte ambos.
        for book_id in data.available_book_ids() - before:
            data.notify_available(book_id)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def initialize():
    """No elimina ni sobrescribe bases existentes, ni siquiera vacías."""
    path = Path(current_app.config['DATABASE'])
    path.parent.mkdir(parents=True, exist_ok=True)
    # Creación exclusiva para evitar reinicializaciones accidentales.
    with path.open('xb'):
        pass
    try:
        with sqlite3.connect(path) as conn:
            conn.execute('PRAGMA journal_mode = WAL')
            conn.executescript(Path(__file__).with_name('schema.sql').read_text(encoding='utf-8'))
            conn.executescript(migration_sql())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def migration_sql():
    return (Path(__file__).parent / 'migrations/002_favorites_security.sql').read_text(encoding='utf-8')


def backup(destination):
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb'):
        pass
    try:
        with sqlite3.connect(destination) as target:
            get_db().backup(target)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


def upgrade():
    from . import data
    from datetime import datetime, timezone
    version = data.metadata('schema_version')
    if version == '2':
        return None
    if version != '1':
        raise RuntimeError('Versión de base no reconocida. No se modificó.')
    filename = 'antes-v2-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3'
    saved = backup(Path(current_app.config['DATABASE']).parent / 'backups' / filename)
    conn = get_db()
    try:
        conn.executescript(migration_sql())
    except BaseException:
        conn.rollback()
        raise
    return saved
