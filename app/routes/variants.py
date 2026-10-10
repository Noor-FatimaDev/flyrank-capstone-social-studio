from fastapi import APIRouter
from pydantic import BaseModel

from app.services.generation import generate_variants
from app.services.review import approve_variant, edit_variant, reject_variant

router = APIRouter()


class EditIn(BaseModel):
    text: str


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