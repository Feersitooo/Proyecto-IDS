BEGIN IMMEDIATE;
ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1));
UPDATE users SET is_demo=1 WHERE email IN
 ('admin@demo.test','ana@demo.test','bruno@demo.test','carla@demo.test');

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
CREATE INDEX notifications_by_user ON availability_notifications(user_id,read_at);
CREATE TABLE login_attempts (
 id INTEGER PRIMARY KEY,
 account_key TEXT NOT NULL,
 client_key TEXT NOT NULL,
 attempted_at TEXT NOT NULL
);
CREATE INDEX attempts_by_account ON login_attempts(account_key,attempted_at);
CREATE INDEX attempts_by_client ON login_attempts(client_key,attempted_at);
UPDATE metadata SET value='2' WHERE key='schema_version';
COMMIT;
