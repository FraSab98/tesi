"""
Entry point della piattaforma.

Avvio locale:
    uvicorn app.main:app --reload --port 8000

Docs Swagger automatiche:
    http://localhost:8000/docs
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.api import patients, sessions, responses, analysis, reports

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Eventi startup/shutdown."""
    logger.info(f"Avvio {settings.app_name}")
    logger.info(f"LLM provider: {settings.llm_provider}")
    # In dev: crea schema DB automaticamente
    if settings.debug:
        try:
            await init_db()
            logger.info("Schema DB inizializzato")
        except Exception as e:
            logger.warning(f"init_db saltato: {e}")
    yield
    logger.info("Shutdown")


app = FastAPI(
    title=settings.app_name,
    description=(
        "Piattaforma per la valutazione delle malattie cognitive "
        "tramite test interattivi generati da LLM."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: in dev permettiamo tutte le origini, in prod restringere
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra router
app.include_router(patients.router, prefix=settings.api_prefix)
app.include_router(sessions.router, prefix=settings.api_prefix)
app.include_router(responses.router, prefix=settings.api_prefix)
app.include_router(analysis.router, prefix=settings.api_prefix) 
app.include_router(reports.router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
        "llm_provider": settings.llm_provider,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
