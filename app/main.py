# app/main.py
from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.templating import Jinja2Templates

from app.core.config import settings
from app.db.session import engine, SessionLocal
from app.db.base import Base
from app.db.init_db import ensure_admin
from app.services.storage import ensure_storage_dir

from app.routers.api_auth import router as api_auth_router
from app.routers.api_public import router as api_public_router
from app.routers.api_metrics import router as api_metrics_router
from app.routers.api_anamnese import router as api_anamnese_router

# ✅ IA (Pedidos/Receitas)
from app.routers.api_pedidos_exame import router as api_pedidos_exame_router

from app.routers.web_auth import router as web_auth_router
from app.routers.web_dashboard import router as web_dashboard_router
from app.routers.web_empresas import router as web_empresas_router
from app.routers.web_campanhas import router as web_campanhas_router
from app.routers.web_materiais import router as web_materiais_router
from app.routers.web_pacientes import router as web_pacientes_router

from app.routers.fin_auth import router as fin_auth_router
from app.routers.fin_caixa import router as fin_caixa_router
from app.routers.fin_relatorios import router as fin_relatorios_router


def _parse_cors_origins(value) -> list[str]:
    """
    Aceita:
      - "*" (libera geral, mas sem credenciais)
      - lista separada por vírgula: "https://site.com,http://localhost:3000"
      - vazio -> defaults locais
    """
    v = (value or "").strip()
    if not v:
        return [
            "http://localhost",
            "http://localhost:3000",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
        ]
    if v == "*":
        return ["*"]
    return [x.strip() for x in v.split(",") if x.strip()]


cors_origins = _parse_cors_origins(getattr(settings, "CORS_ORIGINS", ""))

app = FastAPI(title=settings.APP_NAME)

# =========================
# CORS
# =========================
allow_credentials = True
if cors_origins == ["*"]:
    allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Sessões (cookie) - painéis web
# =========================
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# =========================
# Templates
# =========================
templates = Jinja2Templates(directory="app/templates")
app.state.templates = templates

# =========================
# Static
# =========================
static_dir = Path("app/static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# =========================
# Uploads / Storage
# =========================
storage_dir = Path(ensure_storage_dir())
if storage_dir.exists():
    app.mount("/uploads", StaticFiles(directory=str(storage_dir)), name="uploads")

# =========================
# Routers
# =========================
# API App
app.include_router(api_auth_router)
app.include_router(api_public_router)
app.include_router(api_metrics_router)
app.include_router(api_anamnese_router)
app.include_router(api_pedidos_exame_router)

# Web Admin
app.include_router(web_auth_router)
app.include_router(web_dashboard_router)
app.include_router(web_empresas_router)
app.include_router(web_campanhas_router)
app.include_router(web_materiais_router)
app.include_router(web_pacientes_router)

# Financeiro
app.include_router(fin_auth_router)
app.include_router(fin_caixa_router)
app.include_router(fin_relatorios_router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}


def _safe_create_all_once() -> None:
    """
    Evita corrida (race) quando o gunicorn sobe com múltiplos workers.
    Só tenta criar tabelas se AUTO_CREATE_TABLES=1.
    Usa lock file simples em /tmp.
    """
    if os.getenv("AUTO_CREATE_TABLES", "0") != "1":
        return

    lock_path = "/tmp/dualgr_create_all.lock"
    try:
        # cria lock "atomicamente"
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        # outro worker já fez
        return

    # checkfirst=True é padrão, mas deixamos explícito
    Base.metadata.create_all(bind=engine, checkfirst=True)


@app.on_event("startup")
def on_startup():
    # garante pasta storage (uploads)
    ensure_storage_dir()

    # ⚠️ NÃO rode create_all no Render por padrão.
    # Se você realmente quiser em DEV: export AUTO_CREATE_TABLES=1
    _safe_create_all_once()

    # Seed do admin (se não existir)
    db = SessionLocal()
    try:
        ensure_admin(db)
    finally:
        db.close()
