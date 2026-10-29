"""
SalesIQ FastAPI application entry point.
"""

import logging
import sys
from contextlib import asynccontextmanager

# pyrefly: ignore[missing-import]
from fastapi import FastAPI
# pyrefly: ignore[missing-import]
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS, GROQ_API_KEY
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

# CORS — allow the React dev server and the deployed frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
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
