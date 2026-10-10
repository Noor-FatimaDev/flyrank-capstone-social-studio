from fastapi import APIRouter
from pydantic import BaseModel

from app.services.ingestion import ingest_post

router = APIRouter()


class PostIn(BaseModel):
    url: str | None = None
    markdown: str | None = None


@router.post("/posts", status_code=201)
def create_post_route(body: PostIn):
    post_id = ingest_post(url=body.url, markdown=body.markdown)
    return {"id": post_id}