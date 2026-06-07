from fastapi import APIRouter

from app.services.schema_service import get_schema_service

router = APIRouter()


@router.get("/schema")
async def get_schema() -> dict:
    """Return database tables, columns, keys, and relationships."""
    service = get_schema_service()
    return service.get_full_schema_response()
