from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import PlainTextResponse

from app.api.models import GenerateRequest, GenerateResponse
from app.services.sql_generator import SQLGeneratorService

router = APIRouter()
_generator = SQLGeneratorService()


@router.post("/generate", response_model=GenerateResponse)
async def generate_sql_json(body: GenerateRequest) -> GenerateResponse:
    """
    Convert a natural language request into valid SQL.
    Uses Schema API and Metadata API internally before generation.
    """
    try:
        sql = _generator.generate(body.query)
        return GenerateResponse(sql=sql)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="SQL generation failed") from exc


@router.post("/generate/sql", response_class=PlainTextResponse)
async def generate_sql_plain(body: GenerateRequest) -> Response:
    """
    Same as /generate but returns raw SQL only (text/plain).
    No JSON wrapper — suitable for strict SQL-only consumers.
    """
    try:
        sql = _generator.generate(body.query)
        return PlainTextResponse(content=sql, media_type="text/plain")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="SQL generation failed") from exc


@router.get("/generate")
async def generate_sql_get(q: str) -> PlainTextResponse:
    """
    GET variant for quick testing. Returns SQL only as plain text.
    Example: /generate?q=Show top 10 employees by salary
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    try:
        sql = _generator.generate(q)
        return PlainTextResponse(content=sql, media_type="text/plain")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
