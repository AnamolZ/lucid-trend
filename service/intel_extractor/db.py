import sqlite3
from typing import List, Dict, Optional
from config.settings import INTEL_DB_FILE


def get_connection() -> sqlite3.Connection:
    INTEL_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(INTEL_DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                post_id TEXT PRIMARY KEY,
                profile TEXT NOT NULL,
                published_at TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_profile ON posts(profile);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_published_at ON posts(published_at);")
        conn.commit()


def is_post_seen(post_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM posts WHERE post_id = ? LIMIT 1;", (post_id,))
        return cursor.fetchone() is not None


def save_post(post_id: str, profile: str, published_at: str, text: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO posts (post_id, profile, published_at, text)
                VALUES (?, ?, ?, ?);
                """,
                (post_id, profile, published_at, text),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def get_recent_intel(limit: int = 15) -> List[Dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT post_id, profile, published_at, text, created_at
            FROM posts
            ORDER BY published_at DESC
            LIMIT ?;
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
