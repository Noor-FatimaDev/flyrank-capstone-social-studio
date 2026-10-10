from datetime import datetime, timezone

from app.db.slots import insert_slot_if_new
from app.db.variants import get_variant
from app.services.errors import ConflictError, NotFoundError, ValidationFailedError


def _parse_future_utc(value: str) -> str:
    """Validate an ISO 8601 time with a timezone and return it as UTC in one
    fixed format, so times can be compared as plain text later."""
    try:
        when = datetime.fromisoformat(value)
    except ValueError:
        raise ValidationFailedError(
            "scheduled_at must be an ISO 8601 datetime, e.g. 2026-10-12T09:00:00Z"
        )
    if when.tzinfo is None:
        raise ValidationFailedError(
            "scheduled_at must include a timezone, e.g. 2026-10-12T09:00:00Z "
            "or 2026-10-12T14:00:00+05:00"
        )
    when = when.astimezone(timezone.utc)
    if when <= datetime.now(timezone.utc):
        raise ValidationFailedError("scheduled_at must be in the future")
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def schedule_variant(variant_id: int, scheduled_at: str) -> dict:
    variant = get_variant(variant_id)
    if variant is None:
        raise NotFoundError(f"Variant {variant_id} not found")

    # Only approved variants may be scheduled. The worker re-checks this
    # right before sending, because an edit can send a variant back to draft.
    if variant["status"] != "approved":
        raise ConflictError(
            f"Variant {variant_id} is {variant['status']}; "
            f"only approved variants can be scheduled"
        )

    when = _parse_future_utc(scheduled_at)
    slot_id, created = insert_slot_if_new(variant_id, when)
    return {
        "slot_id": slot_id,
        "variant_id": variant_id,
        "scheduled_at": when,
        "created": created,
    }