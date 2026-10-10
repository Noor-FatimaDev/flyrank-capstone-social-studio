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