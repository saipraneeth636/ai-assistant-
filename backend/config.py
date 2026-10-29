"""
Configuration module for SalesIQ backend.
All sensitive values are read from environment variables.
Never commit actual API keys to source control.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv not installed; rely on system env vars

# ---------------------------------------------------------------------------
# Groq / LLM settings
# ---------------------------------------------------------------------------
_raw_key: str = os.getenv("GROQ_API_KEY", "")
# Treat the placeholder value as "not set" so health check is accurate
GROQ_API_KEY: str = _raw_key if _raw_key and _raw_key != "your_groq_api_key_here" else ""
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# ---------------------------------------------------------------------------
# Database settings
# ---------------------------------------------------------------------------
# Local default: ./sales.db
# Production (Render persistent disk): /var/data/sales.db
# Set DATABASE_PATH=/var/data/sales.db in Render env vars and mount a
# persistent disk at /var/data.  Without a persistent disk, data written to
# the Render filesystem will be lost on every redeploy or restart.
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./sales.db")

# ---------------------------------------------------------------------------
# CSV data path (relative to this file)
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"
CSV_PATH = DATA_DIR / "ai_bi_assistant_sales_data_cleaned.csv"

# ---------------------------------------------------------------------------
# CORS origins — comma-separated list via env var, or use defaults
# ---------------------------------------------------------------------------
_raw_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:4173",
)
CORS_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]
