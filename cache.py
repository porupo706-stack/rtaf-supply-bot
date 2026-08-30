import hashlib
import sqlite3

DB_NAME = "chat_logs.db"


def get_cache(question):

    qhash = hashlib.md5(
        question.strip().lower().encode()
    ).hexdigest()

    conn = sqlite3.connect(DB_NAME)

    cur = conn.cursor()

    cur.execute(
        """
        SELECT answer
        FROM cache
        WHERE question_hash=?
        """,
        (qhash,)
    )

    row = cur.fetchone()

    conn.close()

    return row[0] if row else None


def save_cache(
    question,
    answer
):

    qhash = hashlib.md5(
        question.strip().lower().encode()
    ).hexdigest()

    conn = sqlite3.connect(DB_NAME)

    cur = conn.cursor()

    cur.execute("""
    INSERT OR REPLACE INTO cache
    VALUES (?, ?, ?, datetime('now'))
    """,
    (
        qhash,
        question,
        answer
    ))

    conn.commit()
    conn.close()