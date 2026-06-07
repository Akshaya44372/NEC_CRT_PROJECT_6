from fastapi import APIRouter

from app.api.routes.generate import router as generate_router
from app.api.routes.metadata import router as metadata_router
from app.api.routes.schema import router as schema_router

api_router = APIRouter()
api_router.include_router(schema_router, tags=["Schema"])
api_router.include_router(metadata_router, tags=["Metadata"])
api_router.include_router(generate_router, tags=["Generate"])
