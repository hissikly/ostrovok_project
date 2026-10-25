"""Конфиг из переменных окружения (см. .env.example)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv("DATA_DIR", ROOT / "data"))
SEED = DATA / "seed"
STATIC = Path(os.getenv("STATIC_DIR", ROOT / "app" / "static"))

APP_PORT = int(os.getenv("APP_PORT", "8080"))
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
