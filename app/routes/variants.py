from fastapi import APIRouter

from app.services.generation import generate_variants

router = APIRouter()


@router.post("/posts/{post_id}/variants/generate")
def generate_variants_route(post_id: int):
    return generate_variants(post_id)