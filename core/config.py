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
# запасной LLM-провайдер: включается, когда основной не отвечает (см. core/llm.py)
LLM_FALLBACK = {"base": os.getenv("LLM_FALLBACK_BASE_URL", ""), "key": os.getenv("LLM_FALLBACK_API_KEY", ""),
                "model": os.getenv("LLM_FALLBACK_MODEL", "")}
# единая база: PostgreSQL (postgresql://…), без DB_URL — один файл SQLite для запуска без Docker
DB_URL = os.getenv("DB_URL", "")
