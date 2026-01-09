# app/core/config.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8-sig",  # importante: remove BOM no Windows
        case_sensitive=False,
        extra="ignore",
    )

    # =========================
    # App
    # =========================
    APP_NAME: str = "Dual Saúde"
    ENV: str = "dev"

    # =========================
    # Auth
    # =========================
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # =========================
    # Database
    # =========================
    DATABASE_URL: str = Field(default="sqlite:///./dual_saude.db")

    # =========================
    # Storage / Uploads
    # =========================
    STORAGE_DRIVER: str = "local"
    LOCAL_STORAGE_PATH: str = "./storage"
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # =========================
    # Upload / Arquivos (limites e tipos)
    # =========================
    MAX_UPLOAD_MB: int = 15
    # Lista separada por vírgula
    ALLOWED_UPLOAD_MIME: str = "application/pdf,image/jpeg,image/png"

    # =========================
    # IA - Leitura de pedidos de exame
    # =========================
    # provider: "openai" (padrão) | "off" (desabilita sem remover código)
    AI_PROVIDER: str = "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    AI_TEMPERATURE: float = 0.1

    # OCR (para imagem / PDF escaneado)
    ENABLE_OCR: bool = True
    OCR_LANG: str = "por"


settings = Settings()


def get_database_url() -> str:
    url = (settings.DATABASE_URL or "").strip()

    # Compat Render/Heroku antigos
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    # Força psycopg (SQLAlchemy 2.x)
    if url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    return url


def allowed_mimes() -> set[str]:
    """
    Retorna conjunto de MIMEs aceitos (lowercase).
    Ex: {"application/pdf", "image/jpeg", "image/png"}
    """
    raw = (settings.ALLOWED_UPLOAD_MIME or "").strip()
    if not raw:
        return set()
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def max_upload_bytes() -> int:
    """
    Limite de upload em bytes.
    """
    mb = int(getattr(settings, "MAX_UPLOAD_MB", 15) or 15)
    return mb * 1024 * 1024
