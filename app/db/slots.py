from app.db.connection import get_connection


def insert_slot_if_new(variant_id: int, scheduled_at: str) -> tuple[int, bool]:
    """Create the slot unless this variant already has one at this time.

    The UNIQUE index on (variant_id, scheduled_at) decides, in one step, so
    two simultaneous requests cannot both create it.
    Returns (slot_id, created).
    """
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO slots (variant_id, scheduled_at) VALUES (?, ?)",
            (variant_id, scheduled_at),
        )
        created = cur.rowcount == 1
        conn.commit()
        row = conn.execute(
            "SELECT id FROM slots WHERE variant_id = ? AND scheduled_at = ?",
            (variant_id, scheduled_at),
        ).fetchone()
        return row["id"], created
    finally:
        conn.close()


def get_slot(slot_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM slots WHERE id = ?", (slot_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_due_slots(now: str, limit: int = 20) -> list[int]:
    """Slots that are due AND still need work: no publish yet, or a publish
    waiting to retry whose retry time has passed. Finished, failed, uncertain
    and in-progress slots are not returned."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT s.id FROM slots s "
            "LEFT JOIN publishes p ON p.slot_id = s.id "
            "WHERE s.scheduled_at <= ? "
            "AND (p.id IS NULL OR (p.status = 'pending' "
            "AND (p.retry_at IS NULL OR p.retry_at <= ?))) "
            "ORDER BY s.scheduled_at, s.id LIMIT ?",
            (now, now, limit),
        ).fetchall()
        return [r["id"] for r in rows]
    finally:
        conn.close()