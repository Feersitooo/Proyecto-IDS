"""Adaptador D1 para el prototipo pequeño; reglas y pantallas siguen en Flask."""
import sqlite3
from .db import normalize


class SnapshotConnection:
    def __init__(self, backend, schema):
        self.backend = backend
        self.local = sqlite3.connect(':memory:', isolation_level=None)
        self.local.row_factory = sqlite3.Row
        self.local.create_function('normalize', 1, normalize, deterministic=True)
        self.local.executescript(schema)
        triggers = self.local.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'").fetchall()
        for row in triggers:
            self.local.execute('DROP TRIGGER "' + row['name'] + '"')
        tables = [r[0] for r in self.local.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        snapshot = backend.snapshot(tables)
        self.revision = snapshot[0]['results'][0]['value']
        self.local.execute('PRAGMA foreign_keys=OFF')
        for table, result in zip(tables, snapshot[1:]):
            self.local.execute(f'DELETE FROM "{table}"')
            for row in result['results']:
                columns = ','.join('"' + key + '"' for key in row)
                marks = ','.join('?' for _ in row)
                self.local.execute(f'INSERT INTO "{table}" ({columns}) VALUES ({marks})', tuple(row.values()))
        for row in triggers:
            self.local.execute(row['sql'])
        self.local.execute('PRAGMA foreign_keys=ON')
        self.pending = None

    def execute(self, sql, args=()):
        command = sql.lstrip().split()[0].upper()
        if command == 'BEGIN':
            if self.pending is not None:
                raise sqlite3.OperationalError('Nested transaction')
            self.pending = []
        elif command not in ('SELECT', 'PRAGMA') and self.pending is None:
            raise sqlite3.OperationalError('Escritura fuera de transacción')
        result = self.local.execute(sql, args)
        if command not in ('BEGIN', 'SELECT', 'PRAGMA'):
            self.pending.append((sql, tuple(args)))
        return result

    def commit(self):
        if self.pending:
            # D1 confirma la revisión y todas las escrituras en un único batch.
            # Si otra cuenta cambió los datos, se rechaza todo (HTTP 409).
            self.backend.commit(self.revision, self.pending)
            self.revision += 1
        self.local.commit()
        self.pending = None

    def rollback(self):
        self.local.rollback()
        self.pending = None

    def close(self):
        self.local.close()


class CloudflareBackend:
    def __init__(self, database):
        self.database = database

    def batch(self, statements):
        from pyodide.ffi import run_sync, to_js
        prepared = [self.database.prepare(sql).bind(*args) if args else self.database.prepare(sql)
                    for sql, args in statements]
        try:
            result = run_sync(self.database.batch(to_js(prepared)))
            return result.to_py()
        except Exception as exc:
            if 'stale_revision' in str(exc) or 'constraint' in str(exc).lower():
                raise sqlite3.IntegrityError('Los datos cambiaron. Actualiza la página.') from exc
            raise sqlite3.OperationalError('D1 no pudo completar la operación') from exc

    def snapshot(self, tables):
        statements = [('SELECT value FROM cloud_revision WHERE id=1', ())]
        statements += [(f'SELECT * FROM "{table}"', ()) for table in tables]
        results = self.batch(statements)
        if sum(len(result['results']) for result in results) > 10000:
            raise sqlite3.OperationalError('Prototipo: se superó el límite de 10000 filas')
        return results

    def commit(self, revision, statements):
        self.batch([('UPDATE cloud_revision SET value=? WHERE id=1', (revision + 1,))] + statements)
