from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.routes import posts
from app.services.ingestion import IngestionError

app = FastAPI(title="Social Media Studio")


@app.exception_handler(IngestionError)
async def ingestion_error_handler(request: Request, exc: IngestionError):
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc)})


app.include_router(posts.router)