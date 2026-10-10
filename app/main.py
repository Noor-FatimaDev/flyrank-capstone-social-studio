from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.routes import posts, variants
from app.services.errors import ServiceError

app = FastAPI(title="Social Media Studio")


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc)})


app.include_router(posts.router)
app.include_router(variants.router)