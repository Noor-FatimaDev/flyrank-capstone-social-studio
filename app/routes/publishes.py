from fastapi import APIRouter

from app.services.publishing import attempts_for, history, publish_slot

router = APIRouter()


@router.post("/slots/{slot_id}/publish")
def publish_slot_route(slot_id: int):
    """Publish one slot now. Safe to call twice: the second call sends nothing."""
    return publish_slot(slot_id)


@router.get("/publishes")
def list_publishes_route():
    return history()


@router.get("/publishes/{publish_id}/attempts")
def attempts_route(publish_id: int):
    return attempts_for(publish_id)