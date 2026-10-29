PRAGMA foreign_keys = ON;
BEGIN;
CREATE TABLE user_types (id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE collections (id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE rules (
    user_type TEXT NOT NULL REFERENCES user_types(id),
    collection_id TEXT NOT NULL REFERENCES collections(id),
    max_items INTEGER NOT NULL CHECK(max_items > 0),
    loan_days INTEGER NOT NULL CHECK(loan_days > 0),
    due_hour INTEGER NOT NULL CHECK(due_hour BETWEEN 0 AND 23),
    PRIMARY KEY(user_type, collection_id)
);
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('alumno','admin')),
    user_type TEXT REFERENCES user_types(id),
    account_active INTEGER NOT NULL DEFAULT 1 CHECK(account_active IN (0,1)),
    lending_enabled INTEGER NOT NULL DEFAULT 1 CHECK(lending_enabled IN (0,1)),
    block_reason TEXT NOT NULL DEFAULT '',
    CHECK(role != 'alumno' OR user_type IS NOT NULL)
);
CREATE TABLE books (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 180),
    author TEXT NOT NULL CHECK(length(trim(author)) BETWEEN 1 AND 180),
    category TEXT NOT NULL CHECK(length(trim(category)) BETWEEN 1 AND 80),
    isbn TEXT NOT NULL DEFAULT '',
    publication_year INTEGER CHECK(publication_year BETWEEN 1000 AND 2100),
    description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE copies (
    id INTEGER PRIMARY KEY,
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE RESTRICT,
    code TEXT NOT NULL UNIQUE CHECK(length(trim(code)) BETWEEN 1 AND 40),
    collection_id TEXT NOT NULL REFERENCES collections(id),
    location TEXT NOT NULL CHECK(length(trim(location)) BETWEEN 1 AND 120),
    retired_at TEXT,
    retirement_reason TEXT NOT NULL DEFAULT '',
    CHECK(retired_at IS NULL OR length(trim(retirement_reason)) > 0)
);
CREATE TABLE requests (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE RESTRICT,
    collection_id TEXT NOT NULL REFERENCES collections(id),
    copy_id INTEGER REFERENCES copies(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'pendiente' CHECK(status IN
      ('pendiente','aprobada','rechazada','cancelada','atendida')),
    created_at TEXT NOT NULL,
    approved_at TEXT,
    ready_at TEXT,
    closed_at TEXT,
    rejection_reason TEXT NOT NULL DEFAULT '',
    CHECK(status NOT IN ('aprobada','atendida') OR (copy_id IS NOT NULL AND approved_at IS NOT NULL)),
    CHECK(status != 'pendiente' OR copy_id IS NULL),
    CHECK(status != 'rechazada' OR length(trim(rejection_reason)) > 0),
    CHECK(ready_at IS NULL OR approved_at IS NOT NULL)
);
CREATE UNIQUE INDEX one_open_request_per_title ON requests(user_id, book_id)
    WHERE status IN ('pendiente','aprobada');
CREATE UNIQUE INDEX one_assignment_per_copy ON requests(copy_id) WHERE status = 'aprobada';
CREATE TABLE loans (
    id INTEGER PRIMARY KEY,
    request_id INTEGER NOT NULL UNIQUE REFERENCES requests(id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    copy_id INTEGER NOT NULL REFERENCES copies(id),
    collection_id TEXT NOT NULL REFERENCES collections(id),
    title_snapshot TEXT NOT NULL,
    code_snapshot TEXT NOT NULL,
    delivered_at TEXT NOT NULL,
    due_at TEXT NOT NULL,
    returned_at TEXT,
    status TEXT NOT NULL DEFAULT 'activo' CHECK(status IN ('activo','devuelto')),
    CHECK(due_at > delivered_at),
    CHECK((status = 'activo' AND returned_at IS NULL) OR
          (status = 'devuelto' AND returned_at >= delivered_at))
);
CREATE UNIQUE INDEX one_active_loan_per_copy ON loans(copy_id) WHERE status = 'activo';
CREATE INDEX requests_by_user ON requests(user_id, status);
CREATE INDEX loans_by_user ON loans(user_id, status, due_at);
CREATE INDEX copies_by_book ON copies(book_id, collection_id);
CREATE TABLE audit_events (
    id INTEGER PRIMARY KEY,
    actor_id INTEGER REFERENCES users(id),
    event TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- El estado y la disponibilidad se derivan; no hay contadores duplicados.
CREATE VIEW copy_inventory AS
SELECT c.*, co.name AS collection_name,
 CASE WHEN c.retired_at IS NOT NULL THEN 'baja'
      WHEN EXISTS(SELECT 1 FROM loans l WHERE l.copy_id=c.id AND l.status='activo') THEN 'prestado'
      WHEN EXISTS(SELECT 1 FROM requests r WHERE r.copy_id=c.id AND r.status='aprobada') THEN 'asignado'
      ELSE 'disponible' END AS state
FROM copies c JOIN collections co ON co.id=c.collection_id;

CREATE TRIGGER request_starts_pending BEFORE INSERT ON requests
WHEN NEW.status != 'pendiente'
BEGIN SELECT RAISE(ABORT, 'request_must_start_pending'); END;
CREATE TRIGGER request_transition BEFORE UPDATE ON requests
WHEN NOT (
 (OLD.status='pendiente' AND NEW.status IN ('aprobada','rechazada','cancelada')) OR
 (OLD.status='aprobada' AND NEW.status IN ('aprobada','cancelada','atendida'))
)
BEGIN SELECT RAISE(ABORT, 'invalid_request_transition'); END;
CREATE TRIGGER request_identity_immutable BEFORE UPDATE ON requests
WHEN NEW.user_id != OLD.user_id OR NEW.book_id != OLD.book_id OR
 NEW.collection_id != OLD.collection_id OR NEW.created_at != OLD.created_at OR
 (OLD.copy_id IS NOT NULL AND NEW.copy_id IS NOT OLD.copy_id)
BEGIN SELECT RAISE(ABORT, 'request_identity_immutable'); END;
CREATE TRIGGER request_assignment_guard BEFORE UPDATE ON requests
WHEN NEW.status='aprobada' AND (
 NOT EXISTS(SELECT 1 FROM copies c WHERE c.id=NEW.copy_id AND c.book_id=NEW.book_id
            AND c.collection_id=NEW.collection_id AND c.retired_at IS NULL) OR
 EXISTS(SELECT 1 FROM loans l WHERE l.copy_id=NEW.copy_id AND l.status='activo')
)
BEGIN SELECT RAISE(ABORT, 'copy_unavailable'); END;
CREATE TRIGGER request_fulfilled_guard BEFORE UPDATE ON requests
WHEN NEW.status='atendida' AND NOT EXISTS(SELECT 1 FROM loans WHERE request_id=NEW.id)
BEGIN SELECT RAISE(ABORT, 'delivery_required'); END;
CREATE TRIGGER loan_insert_guard BEFORE INSERT ON loans
WHEN NEW.status!='activo' OR NOT EXISTS(
 SELECT 1 FROM requests r JOIN copies c ON c.id=r.copy_id
 WHERE r.id=NEW.request_id AND r.user_id=NEW.user_id AND r.copy_id=NEW.copy_id
 AND r.collection_id=NEW.collection_id AND r.status='aprobada' AND r.ready_at IS NOT NULL
 AND c.retired_at IS NULL)
BEGIN SELECT RAISE(ABORT, 'approved_ready_request_required'); END;
CREATE TRIGGER loan_fulfills_request AFTER INSERT ON loans
BEGIN UPDATE requests SET status='atendida', closed_at=NEW.delivered_at WHERE id=NEW.request_id; END;
CREATE TRIGGER loan_return_only BEFORE UPDATE ON loans
WHEN OLD.status!='activo' OR NEW.status!='devuelto' OR NEW.returned_at IS NULL OR
 NEW.request_id!=OLD.request_id OR NEW.copy_id!=OLD.copy_id OR NEW.user_id!=OLD.user_id OR
 NEW.collection_id!=OLD.collection_id OR NEW.delivered_at!=OLD.delivered_at OR NEW.due_at!=OLD.due_at OR
 NEW.title_snapshot!=OLD.title_snapshot OR NEW.code_snapshot!=OLD.code_snapshot
BEGIN SELECT RAISE(ABORT, 'only_one_return_allowed'); END;
CREATE TRIGGER copy_edit_guard BEFORE UPDATE ON copies
WHEN NEW.book_id!=OLD.book_id OR EXISTS(SELECT 1 FROM requests WHERE copy_id=OLD.id AND status='aprobada')
 OR EXISTS(SELECT 1 FROM loans WHERE copy_id=OLD.id AND status='activo')
 OR OLD.retired_at IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'copy_cannot_be_edited'); END;
CREATE TRIGGER preserve_books BEFORE DELETE ON books BEGIN SELECT RAISE(ABORT,'history_protected'); END;
CREATE TRIGGER preserve_copies BEFORE DELETE ON copies BEGIN SELECT RAISE(ABORT,'history_protected'); END;
CREATE TRIGGER preserve_users BEFORE DELETE ON users BEGIN SELECT RAISE(ABORT,'history_protected'); END;
CREATE TRIGGER preserve_requests BEFORE DELETE ON requests BEGIN SELECT RAISE(ABORT,'history_protected'); END;
CREATE TRIGGER preserve_loans BEFORE DELETE ON loans BEGIN SELECT RAISE(ABORT,'history_protected'); END;
CREATE TRIGGER preserve_audit BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT,'history_protected'); END;
CREATE TRIGGER audit_immutable BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT,'history_protected'); END;

INSERT INTO user_types VALUES ('pregrado','Estudiante de pregrado');
INSERT INTO collections VALUES ('general','Colección general'),('alta_demanda','Alta demanda');
INSERT INTO rules VALUES ('pregrado','general',6,3,18),('pregrado','alta_demanda',3,3,19);
INSERT INTO metadata VALUES ('schema_version','1');
COMMIT;
