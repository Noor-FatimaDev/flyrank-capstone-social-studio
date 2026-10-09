from pathlib import Path
from app.db.connection import get_connection

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db() -> None:
    schema = SCHEMA_PATH.read_text()
    conn = get_connection()
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialised.")