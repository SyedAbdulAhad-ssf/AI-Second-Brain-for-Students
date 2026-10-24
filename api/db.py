"""Database adapter with PostgreSQL and persistent local SQLite support."""
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT / ".env", override=True)
SCHEMA_PATH = ROOT / "database" / "schema.sql"
SQLITE_PATH = Path(os.getenv("SQLITE_PATH", str(ROOT / "instance" / "secondbrain.sqlite3")))
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None

SQLITE_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER REFERENCES students(id) ON DELETE CASCADE, title TEXT NOT NULL, subject TEXT, raw_content TEXT NOT NULL, summary TEXT, key_points JSON, definitions JSON, flowchart_mermaid TEXT, mindmap_mermaid TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS quizzes (id INTEGER PRIMARY KEY AUTOINCREMENT, note_id INTEGER REFERENCES notes(id) ON DELETE CASCADE, student_id INTEGER REFERENCES students(id) ON DELETE CASCADE, questions JSON NOT NULL, flashcards JSON NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS quiz_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, quiz_id INTEGER REFERENCES quizzes(id) ON DELETE CASCADE, student_id INTEGER REFERENCES students(id) ON DELETE CASCADE, score INTEGER NOT NULL, total_questions INTEGER NOT NULL, wrong_answers JSON, attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS knowledge_gaps (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER REFERENCES students(id) ON DELETE CASCADE, note_id INTEGER REFERENCES notes(id) ON DELETE CASCADE, weak_topic TEXT NOT NULL, status TEXT DEFAULT 'needs_practice', simple_explanation TEXT, recommended_action TEXT, mini_flowchart TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS revision_plans (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER REFERENCES students(id) ON DELETE CASCADE, exam_date DATE NOT NULL, daily_hours INTEGER DEFAULT 2, schedule JSON NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS chat_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER REFERENCES students(id) ON DELETE CASCADE, note_id INTEGER REFERENCES notes(id) ON DELETE CASCADE, role TEXT NOT NULL, message TEXT NOT NULL, source_reference TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
"""

def using_postgres():
    return bool(os.getenv("DATABASE_URL"))

def get_connection():
    if using_postgres():
        if psycopg2 is None:
            raise RuntimeError("Install requirements.txt to use PostgreSQL")
        return psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=RealDictCursor,
                                sslmode=os.getenv("DB_SSLMODE", "require"))
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SQLITE_PATH), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Create all project tables in the selected database, idempotently."""
    if using_postgres():
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = get_connection()
        try:
            conn.executescript(SQLITE_SCHEMA)
        finally:
            conn.close()
    return True

def _run(sql, params=(), fetch="one"):
    if using_postgres():
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                result = cur.fetchall() if fetch == "all" else (None if fetch == "none" else cur.fetchone())
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    sql = sql.replace("%s", "?")
    conn = get_connection()
    try:
        cur = conn.execute(sql, params)
        if fetch == "none":
            conn.commit()
            return None
        rows = cur.fetchall() if fetch == "all" else [cur.fetchone()]
        conn.commit()
        return [dict(row) if row is not None else None for row in rows] if fetch == "all" else (dict(rows[0]) if rows[0] else None)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def query_one(sql, params=()):
    return _run(sql, params)

def query_all(sql, params=()):
    return _run(sql, params, "all")

def execute(sql, params=()):
    return _run(sql, params)

def execute_many(sql, parameter_sets):
    if using_postgres():
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.executemany(sql, parameter_sets)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return
    conn = get_connection()
    try:
        conn.executemany(sql.replace("%s", "?"), parameter_sets)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
