"""Database schema shared by the app and the create_staff script."""
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, student_id TEXT UNIQUE,
    password_hash TEXT, role TEXT DEFAULT 'student', department TEXT);
CREATE TABLE IF NOT EXISTS monthly_updates(id INTEGER PRIMARY KEY, student_id TEXT NOT NULL, month TEXT NOT NULL,
    data TEXT NOT NULL, note TEXT, updated_by INTEGER, updated_at TEXT, UNIQUE(student_id, month));
"""

def init_db(conn):
    conn.executescript(SCHEMA)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(users)")]
    for col, ddl in (("role", "TEXT DEFAULT 'student'"), ("department", "TEXT")):   # upgrade older databases
        if col not in cols: conn.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
    conn.commit()
