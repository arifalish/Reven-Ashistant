from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    OPENROUTER_API_KEY: str = ""\n    NVIDIA_API_KEY: str = "mock-nvidia-key"
    GROQ_API_KEY: str = "mock-groq-key"
    GEMINI_API_KEY: str = "mock-gemini-key"

    TELEGRAM_BOT_TOKEN: str = "mock-telegram-token"

    FIREBASE_CREDS: Optional[str] = None
    UPSTASH_REDIS_URL: str = "redis://mock-url:6379"

    CF_GATEWAY_URL: str = "https://gateway.ai.cloudflare.com/v1/mock-account/mock-gateway"

    API_SECRET: str = "mock-secret"
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = None

    VAULT_MASTER_KEY: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
