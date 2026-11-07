from app.db.connection import get_connection


def record_mock_post(adapter: str, variant_id: int, text: str, idempotency_key: str) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO mock_posts (adapter, variant_id, text, idempotency_key) "
            "VALUES (?, ?, ?, ?)",
            (adapter, variant_id, text, idempotency_key),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def find_mock_post(idempotency_key: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM mock_posts WHERE idempotency_key = ? ORDER BY id LIMIT 1",
            (idempotency_key,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_mock_posts() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM mock_posts ORDER BY id").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()