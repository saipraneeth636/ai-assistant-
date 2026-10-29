"""
SalesIQ FastAPI application entry point.

Run with:
    uvicorn main:app --reload --port 8000

Then visit http://localhost:8000 — the full dashboard will load.
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import GROQ_API_KEY
from database import init_db
from models import HealthResponse
from routes.analytics_routes import router as analytics_router
from routes.chat_routes import router as chat_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Project root = one level above backend/
FRONTEND_DIR = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SalesIQ backend…")
    init_db()
    logger.info("Database ready.")
    if not GROQ_API_KEY:
        logger.warning(
            "GROQ_API_KEY is not set. The chat endpoint will return an error "
            "until the key is configured."
        )
    yield
    logger.info("Shutting down SalesIQ backend.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="SalesIQ API",
    description="AI-powered Business Intelligence Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow everything since frontend is served on the same origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# API Routers  ← registered BEFORE any static/fallback routes
# ---------------------------------------------------------------------------
app.include_router(analytics_router)
app.include_router(chat_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health", response_model=HealthResponse, tags=["health"])
def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "groq_configured": bool(GROQ_API_KEY),
    }


# ---------------------------------------------------------------------------
# Frontend — serve index.html at "/"
#   http://localhost:8000  →  SalesIQ Dashboard
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def serve_frontend():
    """Return the SalesIQ single-page dashboard."""
    return FileResponse(FRONTEND_DIR / "index.html")


# Mount static assets folder (images, extra CSS, etc.) if it exists
_assets = FRONTEND_DIR / "assets"
if _assets.exists():
    app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")
