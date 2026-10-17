from app.db.connection import get_connection


def claim_publish(
    variant_id: int, slot_id: int, key: str, now: str
) -> tuple[dict, bool]:
    """Try to take the right to publish (variant, slot). Returns (row, claimed).

    Two ways to claim, both a single atomic statement:
      1. INSERT a new row as 'in_progress'. The UNIQUE idempotency_key means
         only one caller can ever create it.
      2. If the row exists as 'pending' (it was rate limited) and its retry
         time has passed, UPDATE it back to 'in_progress'.
    Anyone else gets claimed=False and must not send.
    """
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO publishes "
            "(variant_id, slot_id, idempotency_key, status, started_at) "
            "VALUES (?, ?, ?, 'in_progress', ?)",
            (variant_id, slot_id, key, now),
        )
        claimed = cur.rowcount == 1
        if not claimed:
            cur = conn.execute(
                "UPDATE publishes SET status = 'in_progress', started_at = ?, "
                "retry_at = NULL "
                "WHERE idempotency_key = ? AND status = 'pending' "
                "AND (retry_at IS NULL OR retry_at <= ?)",
                (now, key, now),
            )
            claimed = cur.rowcount == 1
        conn.commit()
        row = conn.execute(
            "SELECT * FROM publishes WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return dict(row), claimed
    finally:
        conn.close()


def finish_publish(
    publish_id: int,
    status: str,
    message_id: str | None = None,
    retry_at: str | None = None,
) -> bool:
    """Move an in_progress publish to its final (or retry) status.
    Only works while it is still in_progress. Returns True if changed."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE publishes SET status = ?, "
            "platform_message_id = COALESCE(?, platform_message_id), "
            "retry_at = ? "
            "WHERE id = ? AND status = 'in_progress'",
            (status, message_id, retry_at, publish_id),
        )
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


def record_attempt(publish_id: int, result: str, error: str | None) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO publish_attempts (publish_id, result, error) VALUES (?, ?, ?)",
            (publish_id, result, error),
        )
        conn.commit()
    finally:
        conn.close()


def sweep_stale(cutoff: str) -> int:
    """Mark in_progress publishes started at or before cutoff as 'uncertain'."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE publishes SET status = 'uncertain' "
            "WHERE status = 'in_progress' AND started_at <= ?",
            (cutoff,),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get_publish(publish_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM publishes WHERE id = ?", (publish_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_publish_by_key(key: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM publishes WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_publishes() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM publishes ORDER BY id").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_attempts(publish_id: int) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM publish_attempts WHERE publish_id = ? ORDER BY id",
            (publish_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()