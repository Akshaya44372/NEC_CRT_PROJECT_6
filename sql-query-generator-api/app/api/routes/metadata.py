from fastapi import APIRouter

from app.services.metadata_service import get_metadata_service

router = APIRouter()


@router.get("/metadata")
async def get_metadata() -> dict:
    """Return business definitions and descriptions."""
    service = get_metadata_service()
    return service.get_full_metadata_response()
