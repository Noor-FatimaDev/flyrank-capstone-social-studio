import logging
import time
from datetime import datetime, timezone

from app.config import POLL_INTERVAL_SECONDS
from app.db.slots import list_due_slots
from app.services.publishing import publish_slot, recover_stale_publishes

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worker")


def run_once() -> int:
    try:
        recovered = recover_stale_publishes()
        if recovered:
            log.info("settled %d stale publish(es)", recovered)
    except Exception as exc:
        log.error("recovery failed: %s: %s", exc.__class__.__name__, exc)

    now = datetime.now(timezone.utc).strftime(TIME_FORMAT)
    handled = 0
    for slot_id in list_due_slots(now):
        try:
            result = publish_slot(slot_id)
            log.info(
                "slot %s -> %s (sent_now=%s)",
                slot_id,
                result["status"],
                result["sent_now"],
            )
            handled += 1
        except Exception as exc:
            log.error("slot %s failed: %s: %s", slot_id, exc.__class__.__name__, exc)
    return handled


def main() -> None:
    log.info("worker started; polling every %s seconds", POLL_INTERVAL_SECONDS)
    try:
        while True:
            run_once()
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        log.info("worker stopped")


if __name__ == "__main__":
    main()