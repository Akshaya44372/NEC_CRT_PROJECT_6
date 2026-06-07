from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import api_router
from app.core.config import settings

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Converts natural language requests into valid SQL queries. "
        "Uses /schema and /metadata before generation. "
        "Strict mode: POST /generate/sql returns SQL only."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_model=None)
async def ui():
    index = STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "endpoints": {
            "schema": "GET /schema",
            "metadata": "GET /metadata",
            "generate_json": "POST /generate",
            "generate_sql_only": "POST /generate/sql",
            "generate_get": "GET /generate?q=<natural language>",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
