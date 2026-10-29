"""Repositorio SQLite: todas las consultas de negocio están en este módulo.

Las rutas no ejecutan SQL. Una futura fuente/importador se adaptará aquí,
manteniendo los contratos de diccionarios y los servicios de circulación.
Las escrituras se invocan dentro de db.transaction().
"""
from .db import get_db
from .timeutils import stamp


def one(sql, args=()):
    row = get_db().execute(sql, args).fetchone()
    return dict(row) if row else None


def many(sql, args=()):
    return [dict(row) for row in get_db().execute(sql, args).fetchall()]


def write(sql, args=()):
    return get_db().execute(sql, args)


# Cuentas y auditoría
def user(user_id):
    return one('SELECT * FROM users WHERE id=?', (user_id,))


def user_by_email(email):
    return one('SELECT * FROM users WHERE email=? COLLATE NOCASE', (email,))


def students():
    return many("SELECT u.*, (SELECT count(*) FROM loans l WHERE l.user_id=u.id AND l.status='activo') AS active_loans FROM users u WHERE role='alumno' ORDER BY name")


def add_user(email, name, password_hash, role='alumno', user_type='pregrado', enabled=True, reason='', is_demo=False):
    return write('INSERT INTO users(email,name,password_hash,role,user_type,lending_enabled,block_reason,is_demo) VALUES(?,?,?,?,?,?,?,?)',
                 (email, name, password_hash, role, user_type if role == 'alumno' else None, int(enabled), reason, int(is_demo))).lastrowid


def set_eligibility(user_id, active, enabled, reason):
    write('UPDATE users SET account_active=?,lending_enabled=?,block_reason=?,session_version=session_version+? WHERE id=? AND role=\'alumno\'',
          (int(active), int(enabled), reason, int(not active), user_id))


def audit(actor_id, event, entity_id, detail=''):
    write('INSERT INTO audit_events(actor_id,event,entity_id,detail,created_at) VALUES(?,?,?,?,?)',
          (actor_id, event, entity_id, detail, stamp()))


def audit_log():
    return many('SELECT a.*,u.name AS actor FROM audit_events a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 100')


# Catálogo y ejemplares
def books(q='', category='', availability=''):
    filters, args = [], []
    if q:
        filters.append('(instr(normalize(b.title),normalize(?))>0 OR instr(normalize(b.author),normalize(?))>0 OR instr(normalize(b.category),normalize(?))>0)')
        args += [q, q, q]
    if category:
        filters.append('b.category=?')
        args.append(category)
    if availability in ('available', 'unavailable'):
        expression = "EXISTS(SELECT 1 FROM copy_inventory ci WHERE ci.book_id=b.id AND ci.state='disponible')"
        filters.append(expression if availability == 'available' else 'NOT ' + expression)
    where = ' WHERE ' + ' AND '.join(filters) if filters else ''
    return many("SELECT b.*, (SELECT count(*) FROM copy_inventory c WHERE c.book_id=b.id AND c.state='disponible') AS available, (SELECT count(*) FROM copies c WHERE c.book_id=b.id AND c.retired_at IS NULL) AS total FROM books b" + where + ' ORDER BY normalize(title)', args)


def categories():
    return [r['category'] for r in many('SELECT DISTINCT category FROM books ORDER BY category')]


def book(book_id):
    return one('SELECT * FROM books WHERE id=?', (book_id,))


def add_book(values):
    return write('INSERT INTO books(title,author,category,isbn,publication_year,description) VALUES(?,?,?,?,?,?)',
                 tuple(values[k] for k in ('title','author','category','isbn','publication_year','description'))).lastrowid


def edit_book(book_id, values):
    write('UPDATE books SET title=?,author=?,category=?,isbn=?,publication_year=?,description=? WHERE id=?',
          tuple(values[k] for k in ('title','author','category','isbn','publication_year','description')) + (book_id,))


def copies(book_id, available_only=False, collection=None):
    sql, args = 'SELECT * FROM copy_inventory WHERE book_id=?', [book_id]
    if available_only:
        sql += " AND state='disponible'"
    if collection:
        sql += ' AND collection_id=?'
        args.append(collection)
    return many(sql + ' ORDER BY code', args)


def copy(copy_id):
    return one('SELECT * FROM copy_inventory WHERE id=?', (copy_id,))


def add_copy(book_id, code, collection_id, location):
    return write('INSERT INTO copies(book_id,code,collection_id,location) VALUES(?,?,?,?)',
                 (book_id,code,collection_id,location)).lastrowid


def edit_copy(copy_id, code, collection_id, location):
    write('UPDATE copies SET code=?,collection_id=?,location=? WHERE id=?', (code,collection_id,location,copy_id))


def retire_copy(copy_id, reason):
    write('UPDATE copies SET retired_at=?,retirement_reason=? WHERE id=?', (stamp(),reason,copy_id))


def collections():
    return many('SELECT * FROM collections ORDER BY name')


# Reglas, cupos y habilitación
def rules():
    return many('SELECT r.*,c.name AS collection_name,t.name AS type_name FROM rules r JOIN collections c ON c.id=r.collection_id JOIN user_types t ON t.id=r.user_type ORDER BY r.user_type,c.name')


def rule(user_type, collection_id):
    return one('SELECT * FROM rules WHERE user_type=? AND collection_id=?', (user_type,collection_id))


def change_rule(user_type, collection_id, maximum, days, hour):
    write('INSERT INTO rules VALUES(?,?,?,?,?) ON CONFLICT(user_type,collection_id) DO UPDATE SET max_items=excluded.max_items,loan_days=excluded.loan_days,due_hour=excluded.due_hour',
          (user_type,collection_id,maximum,days,hour))


def commitments(user_id, collection_id, exclude_request=0):
    loans = one("SELECT count(*) AS n FROM loans WHERE user_id=? AND collection_id=? AND status='activo'", (user_id,collection_id))['n']
    assigned = one("SELECT count(*) AS n FROM requests WHERE user_id=? AND collection_id=? AND status='aprobada' AND id!=?", (user_id,collection_id,exclude_request))['n']
    return loans + assigned


def has_overdue(user_id):
    return one("SELECT id FROM loans WHERE user_id=? AND status='activo' AND due_at<? LIMIT 1", (user_id,stamp())) is not None


def has_open_title(user_id, book_id):
    return one("SELECT id FROM requests WHERE user_id=? AND book_id=? AND status IN ('pendiente','aprobada')", (user_id,book_id)) is not None


def has_borrowed_title(user_id, book_id):
    return one("SELECT l.id FROM loans l JOIN copies c ON c.id=l.copy_id WHERE l.user_id=? AND c.book_id=? AND l.status='activo'", (user_id,book_id)) is not None


# Solicitudes y préstamos: lecturas para ambos perfiles
REQUEST_SELECT = '''SELECT r.*,b.title,b.author,u.name AS student_name,u.email,
 c.code,c.location,co.name AS collection_name
 FROM requests r JOIN books b ON b.id=r.book_id JOIN users u ON u.id=r.user_id
 JOIN collections co ON co.id=r.collection_id LEFT JOIN copies c ON c.id=r.copy_id'''
LOAN_SELECT = '''SELECT l.*,u.name AS student_name,u.email,c.book_id,co.name AS collection_name
 FROM loans l JOIN users u ON u.id=l.user_id JOIN copies c ON c.id=l.copy_id
 JOIN collections co ON co.id=l.collection_id'''


def requests(user_id=None, status=None):
    filters, args = [], []
    if user_id is not None:
        filters.append('r.user_id=?'); args.append(user_id)
    if status in ('pendiente','aprobada','rechazada','cancelada','atendida'):
        filters.append('r.status=?'); args.append(status)
    where = ' WHERE ' + ' AND '.join(filters) if filters else ''
    return many(REQUEST_SELECT + where + ' ORDER BY r.id DESC', args)


def request(request_id):
    return one(REQUEST_SELECT + ' WHERE r.id=?', (request_id,))


def loans(user_id=None, status=None):
    filters, args = [], []
    if user_id is not None:
        filters.append('l.user_id=?'); args.append(user_id)
    if status in ('activo','devuelto'):
        filters.append('l.status=?'); args.append(status)
    elif status == 'vencido':
        filters += ["l.status='activo'", 'l.due_at<?']; args.append(stamp())
    where = ' WHERE ' + ' AND '.join(filters) if filters else ''
    return many(LOAN_SELECT + where + ' ORDER BY l.due_at DESC,l.id DESC', args)


def loan(loan_id):
    return one(LOAN_SELECT + ' WHERE l.id=?', (loan_id,))


def add_request(user_id, book_id, collection_id):
    return write('INSERT INTO requests(user_id,book_id,collection_id,created_at) VALUES(?,?,?,?)',
                 (user_id,book_id,collection_id,stamp())).lastrowid


def approve_request(request_id, copy_id):
    write("UPDATE requests SET status='aprobada',copy_id=?,approved_at=? WHERE id=?", (copy_id,stamp(),request_id))


def ready_request(request_id):
    write('UPDATE requests SET ready_at=? WHERE id=?', (stamp(),request_id))


def close_request(request_id, state, reason=''):
    write('UPDATE requests SET status=?,closed_at=?,rejection_reason=? WHERE id=?', (state,stamp(),reason,request_id))


def add_loan(req, due_at):
    return write('''INSERT INTO loans(request_id,user_id,copy_id,collection_id,title_snapshot,code_snapshot,delivered_at,due_at)
      VALUES(?,?,?,?,?,?,?,?)''', (req['id'],req['user_id'],req['copy_id'],req['collection_id'],req['title'],req['code'],stamp(),due_at)).lastrowid


def return_loan(loan_id):
    write("UPDATE loans SET status='devuelto',returned_at=? WHERE id=?", (stamp(),loan_id))


def metadata(key):
    row = one('SELECT value FROM metadata WHERE key=?', (key,))
    return row['value'] if row else None


def mark_seeded():
    write("INSERT INTO metadata VALUES('demo_seeded_at',?)", (stamp(),))


# Favoritos y avisos: nunca asignan un ejemplar.
def favorite_ids(user_id):
    return {r['book_id'] for r in many('SELECT book_id FROM favorites WHERE user_id=?', (user_id,))}


def watched_ids(user_id):
    return {r['book_id'] for r in many('SELECT book_id FROM availability_watches WHERE user_id=?', (user_id,))}


def set_favorite(user_id, book_id, enabled):
    if enabled:
        write('INSERT OR IGNORE INTO favorites VALUES(?,?,?)', (user_id,book_id,stamp()))
    else:
        write('DELETE FROM favorites WHERE user_id=? AND book_id=?', (user_id,book_id))


def set_watch(user_id, book_id, enabled):
    if enabled:
        write('INSERT OR IGNORE INTO availability_watches VALUES(?,?,?)', (user_id,book_id,stamp()))
    else:
        write('DELETE FROM availability_watches WHERE user_id=? AND book_id=?', (user_id,book_id))


def available_book_ids():
    return {r['book_id'] for r in many("SELECT DISTINCT book_id FROM copy_inventory WHERE state='disponible'")}


def notify_available(book_id):
    event_id = write('INSERT INTO availability_events(book_id,created_at) VALUES(?,?)', (book_id,stamp())).lastrowid
    write('''INSERT INTO availability_notifications(user_id,event_id)
             SELECT w.user_id,? FROM availability_watches w JOIN users u ON u.id=w.user_id
             WHERE w.book_id=? AND u.account_active=1''', (event_id,book_id))


def notifications(user_id, unread_only=False):
    return many('''SELECT n.*,e.book_id,e.created_at,b.title,
        EXISTS(SELECT 1 FROM copy_inventory c WHERE c.book_id=b.id AND c.state='disponible') AS available
        FROM availability_notifications n JOIN availability_events e ON e.id=n.event_id
        JOIN books b ON b.id=e.book_id WHERE n.user_id=?'''
        + (' AND n.read_at IS NULL' if unread_only else '') + ' ORDER BY n.id DESC', (user_id,))


def mark_notification_read(user_id, notification_id):
    return write('UPDATE availability_notifications SET read_at=COALESCE(read_at,?) WHERE user_id=? AND id=?',
                 (stamp(),user_id,notification_id)).rowcount


# Protección de acceso y administración de cuentas desde la consola.
def change_password(user_id, password_hash):
    write('UPDATE users SET password_hash=?,session_version=session_version+1 WHERE id=?', (password_hash,user_id))


def disable_demo_accounts():
    return write('UPDATE users SET account_active=0,session_version=session_version+1 WHERE is_demo=1 AND account_active=1').rowcount


def deployment_counts():
    return one("SELECT sum(is_demo=1 AND account_active=1) AS demo_active, sum(is_demo=0 AND account_active=1 AND role='admin') AS admins FROM users")


def login_counts(account_key, client_key, since):
    write('DELETE FROM login_attempts WHERE attempted_at<?', (since,))
    return one('''SELECT count(CASE WHEN account_key=? THEN 1 END) AS account,
        count(CASE WHEN client_key=? THEN 1 END) AS client
        FROM login_attempts WHERE attempted_at>=?''', (account_key,client_key,since))


def add_login_attempt(account_key, client_key):
    write('INSERT INTO login_attempts(account_key,client_key,attempted_at) VALUES(?,?,?)', (account_key,client_key,stamp()))


def clear_account_attempts(account_key):
    write('DELETE FROM login_attempts WHERE account_key=?', (account_key,))
