from datetime import datetime, timedelta, timezone

from app.adapters.base import Outcome, PublishResult
from app.adapters.registry import get_publisher
from app.config import STALE_AFTER_SECONDS
from app.db.publishes import (
    claim_publish,
    finish_publish,
    get_publish,
    get_publish_by_key,
    list_attempts,
    list_publishes,
    record_attempt,
)
from app.db.slots import get_slot
from app.db.variants import get_variant, transition_status
from app.services.errors import NotFoundError

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fmt(moment: datetime) -> str:
    return moment.strftime(TIME_FORMAT)


def _parse(text: str) -> datetime:
    return datetime.strptime(text, TIME_FORMAT).replace(tzinfo=timezone.utc)


def _summary(publish: dict, sent: bool, note: str | None = None) -> dict:
    return {
        "publish_id": publish["id"],
        "status": publish["status"],
        "platform_message_id": publish["platform_message_id"],
        "sent_now": sent,
        "note": note,
    }


def publish_slot(slot_id: int) -> dict:
    """Publish one slot, at most once.

    1. Claim the right to publish with a single atomic statement (the UNIQUE
       idempotency key). Only one caller can win.
    2. Re-check that the variant is still approved, right before sending.
    3. Call the adapter through the SocialPublisher interface.
    4. Record the attempt and the final status.
    A crash between 3 and 4 leaves the row in_progress; it later goes stale
    and becomes 'uncertain', and is never blindly re-sent.
    """
    slot = get_slot(slot_id)
    if slot is None:
        raise NotFoundError(f"Slot {slot_id} not found")
    variant = get_variant(slot["variant_id"])
    if variant is None:
        raise NotFoundError(f"Variant {slot['variant_id']} not found")

    # A missing or invalid adapter configuration should fail loudly, before
    # anything is claimed or sent.
    publisher = get_publisher(variant["platform"])

    key = f"v{variant['id']}:s{slot_id}"
    now = _now()
    publish, claimed = claim_publish(variant["id"], slot_id, key, _fmt(now))

    if not claimed:
        # Already succeeded, failed, uncertain, waiting to retry, or being
        # sent by someone else. Never send again.
        if publish["status"] == "in_progress" and publish["started_at"]:
            age = (now - _parse(publish["started_at"])).total_seconds()
            if age > STALE_AFTER_SECONDS and finish_publish(publish["id"], "uncertain"):
                record_attempt(
                    publish["id"],
                    "stale",
                    "stuck in_progress past the timeout; outcome unknown",
                )
                publish = get_publish_by_key(key)
        return _summary(publish, sent=False, note="not sent: already handled")

    # Time of check vs time of use: approval can change after scheduling.
    fresh = get_variant(variant["id"])
    if fresh["status"] != "approved":
        record_attempt(
            publish["id"], "not_sent", f"variant is {fresh['status']}, not approved"
        )
        finish_publish(publish["id"], "failed")
        return _summary(
            get_publish(publish["id"]),
            sent=False,
            note=f"variant is {fresh['status']}, not approved",
        )

    try:
        result = publisher.publish(fresh, key)
    except Exception as exc:  # an adapter should not raise; if it does, we do not know
        result = PublishResult(
            Outcome.UNKNOWN, error=f"adapter error: {exc.__class__.__name__}"
        )

    record_attempt(publish["id"], result.outcome.value, result.error)

    if result.outcome == Outcome.POSTED:
        finish_publish(publish["id"], "succeeded", message_id=result.message_id)
        transition_status(variant["id"], ("approved",), "published")
    elif result.outcome == Outcome.RATE_LIMITED:
        retry_at = _fmt(now + timedelta(seconds=result.retry_after or 1))
        finish_publish(publish["id"], "pending", retry_at=retry_at)
    elif result.outcome == Outcome.REJECTED:
        finish_publish(publish["id"], "failed")
    else:
        finish_publish(publish["id"], "uncertain")

    return _summary(get_publish(publish["id"]), sent=True, note=result.error)


def history() -> list[dict]:
    return list_publishes()


def attempts_for(publish_id: int) -> list[dict]:
    if get_publish(publish_id) is None:
        raise NotFoundError(f"Publish {publish_id} not found")
    return list_attempts(publish_id)