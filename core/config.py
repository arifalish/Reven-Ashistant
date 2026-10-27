import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    NVIDIA_API_KEY: str = "mock-nvidia-key"
    GROQ_API_KEY: str = "mock-groq-key"
    GEMINI_API_KEY: str = "mock-gemini-key"

    TELEGRAM_BOT_TOKEN: str = "mock-telegram-token"
    ENABLE_TELEGRAM: bool = False
    ENABLE_BROWSER: bool = False
    ENABLE_SCRAPER: bool = False

    FIREBASE_CREDS: Optional[str] = None
    UPSTASH_REDIS_URL: str = "redis://mock-url:6379"

    CF_GATEWAY_URL: str = "https://gateway.ai.cloudflare.com/v1/mock-account/mock-gateway"
    API_SECRET: str = "mock-secret"
    VAULT_MASTER_KEY: Optional[str] = None
    MODE: str = "mock"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

# Runtime-safe toggles based on environment
settings.ENABLE_TELEGRAM = settings.ENABLE_TELEGRAM or bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_BOT_TOKEN != "mock-telegram-token")
settings.ENABLE_BROWSER = settings.ENABLE_BROWSER or os.getenv("ENABLE_BROWSER", "0") == "1"
settings.ENABLE_SCRAPER = settings.ENABLE_SCRAPER or os.getenv("ENABLE_SCRAPER", "0") == "1"
