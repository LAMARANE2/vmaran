"""Application configuration — single source for env-driven settings."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    # Relative sqlite path is resolved by Flask-SQLAlchemy into instance/
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # OpenAI-compatible endpoint (real OpenAI, or a local router such as FreeLLMAPI)
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "")  # empty → official OpenAI
    AI_MODEL_MAIN = os.environ.get("AI_MODEL_MAIN", "gemini-flash-lite")
    AI_MODEL_FAST = os.environ.get("AI_MODEL_FAST", "gemini-flash-lite")

    # Optional automatic failover to a second OpenAI-compatible endpoint (Protocol 5: resilience).
    # Empty AI_FALLBACK_BASE_URL → failover disabled (single-endpoint behaviour).
    AI_FALLBACK_BASE_URL = os.environ.get("AI_FALLBACK_BASE_URL", "")  # e.g. "" → official OpenAI
    AI_FALLBACK_API_KEY = os.environ.get("AI_FALLBACK_API_KEY", "")
    AI_FALLBACK_MODEL_MAIN = os.environ.get("AI_FALLBACK_MODEL_MAIN", "gpt-5.6-terra")
    AI_FALLBACK_MODEL_FAST = os.environ.get("AI_FALLBACK_MODEL_FAST", "gpt-5.6-luna")

    AI_TIMEOUT = float(os.environ.get("AI_TIMEOUT", "20"))
    AI_MAX_RETRIES = int(os.environ.get("AI_MAX_RETRIES", "1"))

    # Logging (Protocol 4)
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_DIR = BASE_DIR / "logs"


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    LOG_LEVEL = "CRITICAL"
    SECRET_KEY = "test"
    OPENAI_API_KEY = ""  # deterministic: the suite never touches the network
    OPENAI_BASE_URL = ""
    AI_MODEL_MAIN = "test-main"
    AI_MODEL_FAST = "test-fast"
    AI_FALLBACK_BASE_URL = ""
    AI_FALLBACK_API_KEY = ""
    AI_FALLBACK_MODEL_MAIN = "test-fallback-main"
    AI_FALLBACK_MODEL_FAST = "test-fallback-fast"
