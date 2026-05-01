from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sports_predict"
    # Set SECRET_KEY in your .env file for production. Never commit a real key to source control.
    SECRET_KEY: str = "dev-only-insecure-key-override-via-dotenv-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Google Gemini (fallback LLM)
    GOOGLE_API_KEY: str = ""
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # OpenRouter — основний LLM провайдер (безкоштовні моделі)
    # Ключ: https://openrouter.ai/keys
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "nvidia/nemotron-3-super-120b-a12b:free"
    # Live analysis uses a fast non-reasoning model for clean streaming
    OPENROUTER_LIVE_MODEL: str = "meta-llama/llama-3.3-70b-instruct:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    AUTO_SYNC_REAL_DATA: bool = True
    AUTO_SIMULATE_PAST_MATCHES: bool = False

    # SMTP / email settings
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    FRONTEND_URL: str = "http://localhost:5173"
    AVATAR_CACHE_DIR: str = "/var/cache/sportpredict/avatars"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
