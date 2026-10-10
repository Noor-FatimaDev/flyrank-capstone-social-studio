from app.db.connection import get_connection


def get_post(post_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_variant(variant_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM variants WHERE id = ?", (variant_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def has_active_variant(post_id: int, platform: str) -> bool:
    """True if the post already has a variant for this platform that is not rejected."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM variants "
            "WHERE post_id = ? AND platform = ? AND status != 'rejected' "
            "LIMIT 1",
            (post_id, platform),
        ).fetchone()
        return row is not None
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


def transition_status(variant_id: int, from_statuses: tuple, to_status: str) -> bool:
    """Change status ONLY if the variant is still in one of from_statuses.

    The check and the change happen in a single UPDATE, so two callers
    cannot both succeed. Returns True if a row was changed.
    """
    marks = ",".join("?" for _ in from_statuses)
    conn = get_connection()
    try:
        cur = conn.execute(
            f"UPDATE variants SET status = ? WHERE id = ? AND status IN ({marks})",
            (to_status, variant_id, *from_statuses),
        )
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


def update_text_and_reset(variant_id: int, text: str, from_statuses: tuple) -> bool:
    """Replace the text and send the variant back to draft, only if its
    status is still one of from_statuses. Returns True if a row was changed."""
    marks = ",".join("?" for _ in from_statuses)
    conn = get_connection()
    try:
        cur = conn.execute(
            f"UPDATE variants SET text = ?, status = 'draft' "
            f"WHERE id = ? AND status IN ({marks})",
            (text, variant_id, *from_statuses),
        )
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()