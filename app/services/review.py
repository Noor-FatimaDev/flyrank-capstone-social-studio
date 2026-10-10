from app.db.variants import (
    get_variant,
    transition_status,
    update_text_and_reset,
)
from app.services.constraints import validate_variant
from app.services.errors import ConflictError, NotFoundError, ValidationFailedError

# Allowed moves:
#   approve: draft -> approved
#   reject:  draft | approved -> rejected
#   edit:    draft | approved -> draft (text replaced, must pass validation)
# 'rejected' and 'published' are final for that variant.


def _load(variant_id: int) -> dict:
    variant = get_variant(variant_id)
    if variant is None:
        raise NotFoundError(f"Variant {variant_id} not found")
    return variant


def _check_rules(platform: str, text: str) -> None:
    if not text or not text.strip():
        raise ValidationFailedError("The variant text is empty")
    errors = validate_variant(platform, text)
    if errors:
        raise ValidationFailedError("; ".join(errors))


def approve_variant(variant_id: int) -> dict:
    variant = _load(variant_id)
    if variant["status"] != "draft":
        raise ConflictError(
            f"Variant {variant_id} is {variant['status']}; "
            f"only draft variants can be approved"
        )
    # Final gate: re-check the rules at approval time.
    _check_rules(variant["platform"], variant["text"])

    if not transition_status(variant_id, ("draft",), "approved"):
        raise ConflictError(
            f"Variant {variant_id} changed state while approving; try again"
        )
    return get_variant(variant_id)


def reject_variant(variant_id: int) -> dict:
    variant = _load(variant_id)
    if variant["status"] not in ("draft", "approved"):
        raise ConflictError(
            f"Variant {variant_id} is {variant['status']}; "
            f"only draft or approved variants can be rejected"
        )
    if not transition_status(variant_id, ("draft", "approved"), "rejected"):
        raise ConflictError(
            f"Variant {variant_id} changed state while rejecting; try again"
        )
    return get_variant(variant_id)


def edit_variant(variant_id: int, text: str) -> dict:
    variant = _load(variant_id)
    if variant["status"] not in ("draft", "approved"):
        raise ConflictError(
            f"Variant {variant_id} is {variant['status']}; "
            f"only draft or approved variants can be edited"
        )
    _check_rules(variant["platform"], text)

    if not update_text_and_reset(variant_id, text, ("draft", "approved")):
        raise ConflictError(
            f"Variant {variant_id} changed state while editing; try again"
        )
    return get_variant(variant_id)