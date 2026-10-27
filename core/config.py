import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    NVIDIA_API_KEY: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    CF_GATEWAY_URL: str = ""
    API_SECRET: str = "dev-secret"
    UPSTASH_REDIS_URL: str = ""
    FIREBASE_CREDS: Optional[str] = None
    VAULT_MASTER_KEY: Optional[str] = None
    ENABLE_TELEGRAM: bool = False
    ENABLE_BROWSER: bool = False
    ENABLE_SCRAPER: bool = False
    MODE: str = "dev"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()


def has_real_value(value: Optional[str]) -> bool:
    if not value:
        return False
    value = value.strip().lower()
    return not any(token in value for token in ["mock", "example", "placeholder", "your_"])


settings.ENABLE_TELEGRAM = settings.ENABLE_TELEGRAM or bool(has_real_value(settings.TELEGRAM_BOT_TOKEN))
settings.ENABLE_BROWSER = settings.ENABLE_BROWSER or bool(has_real_value(settings.NVIDIA_API_KEY))
settings.ENABLE_SCRAPER = settings.ENABLE_SCRAPER or bool(has_real_value(settings.NVIDIA_API_KEY))

if has_real_value(settings.NVIDIA_API_KEY):
    settings.MODE = "prod"
elif has_real_value(settings.TELEGRAM_BOT_TOKEN):
    settings.MODE = "semi-prod"
else:
    settings.MODE = "mock"

if settings.CF_GATEWAY_URL and settings.CF_GATEWAY_URL.endswith("/"):
    settings.CF_GATEWAY_URL = settings.CF_GATEWAY_URL.rstrip("/")
