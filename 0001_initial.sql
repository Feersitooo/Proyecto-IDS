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
    block_reason TEXT NOT NULL DEFAULT '', session_version INTEGER NOT NULL DEFAULT 1, is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1)),
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
CREATE TABLE audit_events (
    id INTEGER PRIMARY KEY,
    actor_id INTEGER REFERENCES users(id),
    event TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE favorites (
 user_id INTEGER NOT NULL REFERENCES users(id),
 book_id INTEGER NOT NULL REFERENCES books(id),
 created_at TEXT NOT NULL,
 PRIMARY KEY(user_id,book_id)
);
CREATE TABLE availability_watches (
 user_id INTEGER NOT NULL REFERENCES users(id),
 book_id INTEGER NOT NULL REFERENCES books(id),
 created_at TEXT NOT NULL,
 PRIMARY KEY(user_id,book_id)
);
CREATE TABLE availability_events (
 id INTEGER PRIMARY KEY,
 book_id INTEGER NOT NULL REFERENCES books(id),
 created_at TEXT NOT NULL
);
CREATE TABLE availability_notifications (
 id INTEGER PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id),
 event_id INTEGER NOT NULL REFERENCES availability_events(id),
 read_at TEXT,
 UNIQUE(user_id,event_id)
);
CREATE TABLE login_attempts (
 id INTEGER PRIMARY KEY,
 account_key TEXT NOT NULL,
 client_key TEXT NOT NULL,
 attempted_at TEXT NOT NULL
);
INSERT INTO "user_types" VALUES('pregrado','Estudiante de pregrado');
INSERT INTO "collections" VALUES('general','Colección general');
INSERT INTO "collections" VALUES('alta_demanda','Alta demanda');
INSERT INTO "books" VALUES(1,'Fundamentos de cálculo','Elena Mistral','Matemáticas','DEMO-001',2020,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "books" VALUES(2,'Probabilidad para comprender el mundo','Tomás Vega','Matemáticas','DEMO-002',2021,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "books" VALUES(3,'Estructuras de datos en práctica','Paula Ríos','Computación','DEMO-003',2022,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "books" VALUES(4,'Diseño digital paso a paso','Martín Salas','Computación','DEMO-004',2023,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "books" VALUES(5,'Ingeniería para un futuro sostenible','Lucía Marín','Sostenibilidad','DEMO-005',2024,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "books" VALUES(6,'Álgebra lineal aplicada','Andrés Torres','Matemáticas','DEMO-006',2025,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "books" VALUES(7,'Física: movimiento y energía','Valentina Soto','Ciencias','DEMO-007',2020,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "books" VALUES(8,'Introducción a las bases de datos','Diego Araya','Computación','DEMO-008',2021,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "books" VALUES(9,'Economía y sociedad','Camila Solís','Ciencias sociales','DEMO-009',2022,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "books" VALUES(10,'Química en nuestro entorno','Sergio Molina','Ciencias','DEMO-010',2023,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "books" VALUES(11,'Comunicación académica','Isabel Fuentes','Humanidades','DEMO-011',2024,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "books" VALUES(12,'Ecología de la costa chilena','Javier Lagos','Sostenibilidad','DEMO-012',2025,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "books" VALUES(13,'Métodos de investigación','Francisca Luna','Ciencias sociales','DEMO-013',2020,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "books" VALUES(14,'Programación con Python','Rafael Oliva','Computación','DEMO-014',2021,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "books" VALUES(15,'Ética y responsabilidad profesional','Antonia Vera','Humanidades','DEMO-015',2022,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "books" VALUES(16,'Estadística para la ingeniería','Matías Prado','Matemáticas','DEMO-016',2023,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "books" VALUES(17,'Accesibilidad y diseño universal','Daniela Campos','Sostenibilidad','DEMO-017',2024,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "books" VALUES(18,'Historia del Norte Chico','Felipe Vidal','Humanidades','DEMO-018',2025,'Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.');
INSERT INTO "metadata" VALUES('schema_version','2');
INSERT INTO "metadata" VALUES('demo_seeded_at','2026-10-29T13:22:22Z');
INSERT INTO "rules" VALUES('pregrado','general',6,3,18);
INSERT INTO "rules" VALUES('pregrado','alta_demanda',3,3,19);
INSERT INTO "users" VALUES(1,'admin@demo.test','María Demo','disabled-until-reset','admin',NULL,0,1,'',2,1);
INSERT INTO "users" VALUES(2,'ana@demo.test','Ana Pérez Demo','disabled-until-reset','alumno','pregrado',0,1,'',2,1);
INSERT INTO "users" VALUES(3,'bruno@demo.test','Bruno Díaz Demo','disabled-until-reset','alumno','pregrado',0,1,'',2,1);
INSERT INTO "users" VALUES(4,'carla@demo.test','Carla Muñoz Demo','disabled-until-reset','alumno','pregrado',0,0,'Bloqueo ficticio para validar solicitudes y entregas.',2,1);
INSERT INTO "copies" VALUES(1,1,'COQ-DEMO-001-01','general','Campus Guayacán · Estante A-1',NULL,'');
INSERT INTO "copies" VALUES(2,1,'COQ-DEMO-001-02','general','Campus Guayacán · Estante A-1',NULL,'');
INSERT INTO "copies" VALUES(3,1,'COQ-DEMO-001-03','general','Campus Guayacán · Estante A-1',NULL,'');
INSERT INTO "copies" VALUES(4,2,'COQ-DEMO-002-01','general','Campus Guayacán · Estante A-2',NULL,'');
INSERT INTO "copies" VALUES(5,2,'COQ-DEMO-002-02','general','Campus Guayacán · Estante A-2',NULL,'');
INSERT INTO "copies" VALUES(6,2,'COQ-DEMO-002-03','general','Campus Guayacán · Estante A-2',NULL,'');
INSERT INTO "copies" VALUES(7,3,'COQ-DEMO-003-01','alta_demanda','Campus Guayacán · Estante A-3',NULL,'');
INSERT INTO "copies" VALUES(8,3,'COQ-DEMO-003-02','alta_demanda','Campus Guayacán · Estante A-3','2026-10-29T13:22:22Z','Ejemplo de título sin disponibilidad para probar los avisos.');
INSERT INTO "copies" VALUES(9,3,'COQ-DEMO-003-03','alta_demanda','Campus Guayacán · Estante A-3','2026-10-29T13:22:22Z','Ejemplo de título sin disponibilidad para probar los avisos.');
INSERT INTO "copies" VALUES(10,4,'COQ-DEMO-004-01','general','Campus Guayacán · Estante A-4',NULL,'');
INSERT INTO "copies" VALUES(11,4,'COQ-DEMO-004-02','general','Campus Guayacán · Estante A-4',NULL,'');
INSERT INTO "copies" VALUES(12,4,'COQ-DEMO-004-03','general','Campus Guayacán · Estante A-4',NULL,'');
INSERT INTO "copies" VALUES(13,5,'COQ-DEMO-005-01','alta_demanda','Campus Guayacán · Estante B-1',NULL,'');
INSERT INTO "copies" VALUES(14,5,'COQ-DEMO-005-02','alta_demanda','Campus Guayacán · Estante B-1',NULL,'');
INSERT INTO "copies" VALUES(15,5,'COQ-DEMO-005-03','alta_demanda','Campus Guayacán · Estante B-1',NULL,'');
INSERT INTO "copies" VALUES(16,6,'COQ-DEMO-006-01','general','Campus Guayacán · Estante B-2',NULL,'');
INSERT INTO "copies" VALUES(17,6,'COQ-DEMO-006-02','general','Campus Guayacán · Estante B-2',NULL,'');
INSERT INTO "copies" VALUES(18,6,'COQ-DEMO-006-03','general','Campus Guayacán · Estante B-2',NULL,'');
INSERT INTO "copies" VALUES(19,7,'COQ-DEMO-007-01','general','Campus Guayacán · Estante B-3',NULL,'');
INSERT INTO "copies" VALUES(20,7,'COQ-DEMO-007-02','general','Campus Guayacán · Estante B-3',NULL,'');
INSERT INTO "copies" VALUES(21,8,'COQ-DEMO-008-01','general','Campus Guayacán · Estante B-4',NULL,'');
INSERT INTO "copies" VALUES(22,8,'COQ-DEMO-008-02','general','Campus Guayacán · Estante B-4',NULL,'');
INSERT INTO "copies" VALUES(23,9,'COQ-DEMO-009-01','general','Campus Guayacán · Estante C-1',NULL,'');
INSERT INTO "copies" VALUES(24,9,'COQ-DEMO-009-02','general','Campus Guayacán · Estante C-1',NULL,'');
INSERT INTO "copies" VALUES(25,10,'COQ-DEMO-010-01','general','Campus Guayacán · Estante C-2',NULL,'');
INSERT INTO "copies" VALUES(26,10,'COQ-DEMO-010-02','general','Campus Guayacán · Estante C-2',NULL,'');
INSERT INTO "copies" VALUES(27,11,'COQ-DEMO-011-01','general','Campus Guayacán · Estante C-3',NULL,'');
INSERT INTO "copies" VALUES(28,11,'COQ-DEMO-011-02','general','Campus Guayacán · Estante C-3',NULL,'');
INSERT INTO "copies" VALUES(29,12,'COQ-DEMO-012-01','general','Campus Guayacán · Estante C-4',NULL,'');
INSERT INTO "copies" VALUES(30,12,'COQ-DEMO-012-02','general','Campus Guayacán · Estante C-4',NULL,'');
INSERT INTO "copies" VALUES(31,13,'COQ-DEMO-013-01','alta_demanda','Campus Guayacán · Estante D-1',NULL,'');
INSERT INTO "copies" VALUES(32,13,'COQ-DEMO-013-02','alta_demanda','Campus Guayacán · Estante D-1',NULL,'');
INSERT INTO "copies" VALUES(33,14,'COQ-DEMO-014-01','general','Campus Guayacán · Estante D-2',NULL,'');
INSERT INTO "copies" VALUES(34,14,'COQ-DEMO-014-02','general','Campus Guayacán · Estante D-2',NULL,'');
INSERT INTO "copies" VALUES(35,15,'COQ-DEMO-015-01','alta_demanda','Campus Guayacán · Estante D-3',NULL,'');
INSERT INTO "copies" VALUES(36,15,'COQ-DEMO-015-02','alta_demanda','Campus Guayacán · Estante D-3',NULL,'');
INSERT INTO "copies" VALUES(37,16,'COQ-DEMO-016-01','general','Campus Guayacán · Estante D-4',NULL,'');
INSERT INTO "copies" VALUES(38,16,'COQ-DEMO-016-02','general','Campus Guayacán · Estante D-4',NULL,'');
INSERT INTO "copies" VALUES(39,17,'COQ-DEMO-017-01','alta_demanda','Campus Guayacán · Estante E-1',NULL,'');
INSERT INTO "copies" VALUES(40,17,'COQ-DEMO-017-02','alta_demanda','Campus Guayacán · Estante E-1',NULL,'');
INSERT INTO "copies" VALUES(41,18,'COQ-DEMO-018-01','general','Campus Guayacán · Estante E-2',NULL,'');
INSERT INTO "copies" VALUES(42,18,'COQ-DEMO-018-02','general','Campus Guayacán · Estante E-2','2026-10-29T13:22:22Z','Deterioro físico. Caso ficticio de demostración.');
INSERT INTO "availability_events" VALUES(1,1,'2026-10-29T13:22:22Z');
INSERT INTO "availability_events" VALUES(2,2,'2026-10-29T13:22:22Z');
INSERT INTO "availability_events" VALUES(3,4,'2026-10-29T13:22:22Z');
INSERT INTO "availability_events" VALUES(4,5,'2026-10-29T13:22:22Z');
INSERT INTO "availability_events" VALUES(5,6,'2026-10-29T13:22:22Z');
INSERT INTO "availability_events" VALUES(6,7,'2026-10-29T13:22:22Z');
INSERT INTO "availability_events" VALUES(7,8,'2026-10-29T13:22:22Z');
INSERT INTO "availability_events" VALUES(8,9,'2026-10-29T13:22:22Z');
INSERT INTO "availability_events" VALUES(9,10,'2026-10-29T13:22:22Z');
INSERT INTO "availability_events" VALUES(10,11,'2026-10-29T13:22:22Z');
INSERT INTO "availability_events" VALUES(11,12,'2026-10-29T13:22:22Z');
INSERT INTO "availability_events" VALUES(12,13,'2026-10-29T13:22:22Z');
INSERT INTO "availability_events" VALUES(13,14,'2026-10-29T13:22:22Z');
INSERT INTO "availability_events" VALUES(14,15,'2026-10-29T13:22:22Z');
INSERT INTO "availability_events" VALUES(15,16,'2026-10-29T13:22:22Z');
INSERT INTO "availability_events" VALUES(16,17,'2026-10-29T13:22:22Z');
INSERT INTO "availability_events" VALUES(17,18,'2026-10-29T13:22:22Z');
INSERT INTO "requests" VALUES(1,2,1,'general',1,'atendida','2026-10-22T13:22:22Z','2026-10-23T13:22:22Z','2026-10-23T13:22:22Z','2026-10-23T13:22:22Z','');
INSERT INTO "requests" VALUES(2,2,2,'general',4,'atendida','2026-10-22T13:22:22Z','2026-10-23T13:22:22Z','2026-10-23T13:22:22Z','2026-10-23T13:22:22Z','');
INSERT INTO "requests" VALUES(3,3,3,'alta_demanda',7,'atendida','2026-10-22T13:22:22Z','2026-10-23T13:22:22Z','2026-10-23T13:22:22Z','2026-10-23T13:22:22Z','');
INSERT INTO "requests" VALUES(4,2,4,'general',10,'aprobada','2026-10-22T13:22:22Z','2026-10-23T13:22:22Z',NULL,NULL,'');
INSERT INTO "requests" VALUES(5,2,5,'alta_demanda',13,'aprobada','2026-10-22T13:22:22Z','2026-10-23T13:22:22Z','2026-10-23T13:22:22Z',NULL,'');
INSERT INTO "requests" VALUES(6,4,7,'general',19,'aprobada','2026-10-22T13:22:22Z','2026-10-23T13:22:22Z','2026-10-23T13:22:22Z',NULL,'');
INSERT INTO "requests" VALUES(7,4,8,'general',NULL,'pendiente','2026-10-22T13:22:22Z',NULL,NULL,NULL,'');
INSERT INTO "requests" VALUES(8,3,9,'general',NULL,'pendiente','2026-10-22T13:22:22Z',NULL,NULL,NULL,'');
INSERT INTO "requests" VALUES(9,3,10,'general',NULL,'cancelada','2026-10-22T13:22:22Z',NULL,NULL,'2026-10-22T13:22:22Z','');
INSERT INTO "requests" VALUES(10,3,11,'general',NULL,'rechazada','2026-10-22T13:22:22Z',NULL,NULL,'2026-10-22T13:22:22Z','No fue posible preparar el material solicitado. Caso de demostración.');
INSERT INTO "requests" VALUES(11,3,12,'general',29,'atendida','2026-10-22T13:22:22Z','2026-10-23T13:22:22Z','2026-10-23T13:22:22Z','2026-10-23T13:22:22Z','');
INSERT INTO "audit_events" VALUES(1,1,'demostracion_cargada',0,'18 títulos; 42 ejemplares; cuentas y operaciones ficticias.','2026-10-29T13:22:22Z');
INSERT INTO "loans" VALUES(1,1,2,1,'general','Fundamentos de cálculo','COQ-DEMO-001-01','2026-10-23T13:22:22Z','2026-10-30T19:22:22Z',NULL,'activo');
INSERT INTO "loans" VALUES(2,2,2,4,'general','Probabilidad para comprender el mundo','COQ-DEMO-002-01','2026-10-23T13:22:22Z','2026-10-30T02:59:59Z',NULL,'activo');
INSERT INTO "loans" VALUES(3,3,3,7,'alta_demanda','Estructuras de datos en práctica','COQ-DEMO-003-01','2026-10-23T13:22:22Z','2026-10-28T11:22:22Z',NULL,'activo');
INSERT INTO "loans" VALUES(4,11,3,29,'general','Ecología de la costa chilena','COQ-DEMO-012-01','2026-10-23T13:22:22Z','2026-10-27T13:22:22Z','2026-10-26T13:22:22Z','devuelto');
CREATE UNIQUE INDEX one_open_request_per_title ON requests(user_id, book_id)
    WHERE status IN ('pendiente','aprobada');
CREATE UNIQUE INDEX one_assignment_per_copy ON requests(copy_id) WHERE status = 'aprobada';
CREATE UNIQUE INDEX one_active_loan_per_copy ON loans(copy_id) WHERE status = 'activo';
CREATE INDEX requests_by_user ON requests(user_id, status);
CREATE INDEX loans_by_user ON loans(user_id, status, due_at);
CREATE INDEX copies_by_book ON copies(book_id, collection_id);
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
CREATE INDEX notifications_by_user ON availability_notifications(user_id,read_at);
CREATE INDEX attempts_by_account ON login_attempts(account_key,attempted_at);
CREATE INDEX attempts_by_client ON login_attempts(client_key,attempted_at);
CREATE TABLE cloud_revision(id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER NOT NULL);
INSERT INTO cloud_revision VALUES(1,0);
CREATE TRIGGER cloud_revision_guard BEFORE UPDATE ON cloud_revision
WHEN NEW.value != OLD.value + 1 OR NEW.id != OLD.id
BEGIN SELECT RAISE(ABORT,'stale_revision'); END;
CREATE TRIGGER cloud_revision_preserve BEFORE DELETE ON cloud_revision
BEGIN SELECT RAISE(ABORT,'revision_required'); END;
