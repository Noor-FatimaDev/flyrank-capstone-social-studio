import sys
from datetime import datetime, timedelta, timezone

from app.db.init_db import init_db
from app.services.generation import generate_variants
from app.services.ingestion import ingest_post
from app.services.review import approve_variant
from app.services.scheduling import schedule_variant

POSTS = [
    ("Demo post one", "Why idempotency matters."),
    ("Demo post two", "Retries without double posts."),
]


def seed(seconds_ahead: int = 20) -> None:
    init_db()
    when = (datetime.now(timezone.utc) + timedelta(seconds=seconds_ahead)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    slots = []
    for title, summary in POSTS:
        post_id = ingest_post(markdown=f"# {title}\n\n{summary}")
        for variant in generate_variants(post_id)["created"]:
            approve_variant(variant["id"])
            slots.append(schedule_variant(variant["id"], when)["slot_id"])
    print(f"Seeded {len(slots)} slots due at {when}: {slots}")


if __name__ == "__main__":
    seed(int(sys.argv[1]) if len(sys.argv) > 1 else 20)