from app.db.connection import get_connection


def get_post(post_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_variant(post_id: int, platform: str, text: str) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO variants (post_id, platform, text) VALUES (?, ?, ?)",
            (post_id, platform, text),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()