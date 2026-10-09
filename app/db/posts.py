from app.db.connection import get_connection


def create_post(source_url: str | None, body_markdown: str) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO posts (source_url, body_markdown) VALUES (?, ?)",
            (source_url, body_markdown),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()