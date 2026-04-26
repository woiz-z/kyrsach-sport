from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sports_predict"
    # Set SECRET_KEY in your .env file for production. Never commit a real key to source control.
    SECRET_KEY: str = "dev-only-insecure-key-override-via-dotenv-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "openrouter/hunter-alpha"
    AUTO_SYNC_REAL_DATA: bool = True
    AUTO_SIMULATE_PAST_MATCHES: bool = False
    AUTO_RETRY_ESPORTS_IMPORT: bool = True
    ESPORTS_RETRY_INITIAL_DELAY_SECONDS: int = 45
    ESPORTS_RETRY_MAX_DELAY_SECONDS: int = 1800
    AUTO_RETRAIN_MODELS: bool = False
    MODEL_RETRAIN_INTERVAL_SECONDS: int = 86400
    MODEL_RETRAIN_MIN_SAMPLES: int = 30
    AUTO_SYNC_FOOTBALL_DATA: bool = False
    FOOTBALL_DATA_MIN_SEASON: int = 2324
    FOOTBALL_DATA_MAX_LINKS: int = 0

    # SMTP / email settings
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    FRONTEND_URL: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
