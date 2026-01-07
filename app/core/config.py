from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    APP_NAME: str = "Dual Saúde"
    ENV: str = "dev"
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    DATABASE_URL: str = Field(default="sqlite:///./dual_saude.db")

    # Render / proxies
    TRUSTED_HOSTS: str = "*"

    class Config:
        env_file = ".env"


settings = Settings()


def get_database_url() -> str:
    url = settings.DATABASE_URL.strip()
    # Render geralmente fornece postgres:// (deprecated). Normalizar:
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    # SQLAlchemy + psycopg (v3)
    if url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url
