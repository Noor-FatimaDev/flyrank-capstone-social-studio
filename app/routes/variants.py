from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.services.generation import generate_variants
from app.services.review import approve_variant, edit_variant, reject_variant
from app.services.scheduling import schedule_variant

router = APIRouter()


class EditIn(BaseModel):
    text: str


class ScheduleIn(BaseModel):
    scheduled_at: str


@router.post("/posts/{post_id}/variants/generate")
def generate_variants_route(post_id: int):
    return generate_variants(post_id)


@router.post("/variants/{variant_id}/approve")
def approve_route(variant_id: int):
    return approve_variant(variant_id)


@router.post("/variants/{variant_id}/reject")
def reject_route(variant_id: int):
    return reject_variant(variant_id)


@router.patch("/variants/{variant_id}")
def edit_route(variant_id: int, body: EditIn):
    return edit_variant(variant_id, body.text)


@router.post("/variants/{variant_id}/schedule")
def schedule_route(variant_id: int, body: ScheduleIn, response: Response):
    result = schedule_variant(variant_id, body.scheduled_at)
    response.status_code = 201 if result["created"] else 200
    return result