import sqlite3
from datetime import datetime

DB_NAME = "chat_logs.db"


def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def init_db():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        question TEXT,
        answer TEXT,
        notebook_id TEXT,
        cache_hit INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cache(
        question_hash TEXT PRIMARY KEY,
        question TEXT,
        answer TEXT,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()


def save_log(
    question,
    answer,
    notebook_id,
    cache_hit=False
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO chat_logs(
        timestamp,
        question,
        answer,
        notebook_id,
        cache_hit
    )
    VALUES (?, ?, ?, ?, ?)
    """,
    (
        datetime.now().isoformat(),
        question,
        answer,
        notebook_id,
        int(cache_hit)
    ))

    conn.commit()
    conn.close()