# app/main.py
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.templating import Jinja2Templates

from app.core.config import settings
from app.db.session import engine, SessionLocal
from app.db.base import Base
from app.db.init_db import ensure_admin
from app.services.storage import ensure_storage_dir

# 🔧 FIX SQLite legado (Render)
from app.db.sqlite_fix import ensure_sqlite_columns

# =========================
# Routers API (App)
# =========================
from app.routers.api_auth import router as api_auth_router
from app.routers.api_public import router as api_public_router
from app.routers.api_metrics import router as api_metrics_router
from app.routers.api_anamnese import router as api_anamnese_router
from app.routers.api_pedidos_exame import router as api_pedidos_exame_router

# =========================
# Routers Web (Admin)
# =========================
from app.routers.web_auth import router as web_auth_router
from app.routers.web_dashboard import router as web_dashboard_router
from app.routers.web_empresas import router as web_empresas_router
from app.routers.web_campanhas import router as web_campanhas_router
from app.routers.web_materiais import router as web_materiais_router
from app.routers.web_pacientes import router as web_pacientes_router

# =========================
# Routers Financeiro
# =========================
from app.routers.fin_auth import router as fin_auth_router
from app.routers.fin_caixa import router as fin_caixa_router
from app.routers.fin_relatorios import router as fin_relatorios_router


def _parse_cors_origins(value) -> list[str]:
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
allow_credentials = cors_origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Sessões Web
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
# Uploads
# =========================
storage_dir = Path(ensure_storage_dir())
if storage_dir.exists():
    app.mount("/uploads", StaticFiles(directory=str(storage_dir)), name="uploads")

# =========================
# Routers
# =========================
app.include_router(api_auth_router)
app.include_router(api_public_router)
app.include_router(api_metrics_router)
app.include_router(api_anamnese_router)
app.include_router(api_pedidos_exame_router)

app.include_router(web_auth_router)
app.include_router(web_dashboard_router)
app.include_router(web_empresas_router)
app.include_router(web_campanhas_router)
app.include_router(web_materiais_router)
app.include_router(web_pacientes_router)

app.include_router(fin_auth_router)
app.include_router(fin_caixa_router)
app.include_router(fin_relatorios_router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}


@app.on_event("startup")
def on_startup():
    # garante storage
    ensure_storage_dir()

    # 🔧 Corrige SQLite antigo (colunas faltantes)
    ensure_sqlite_columns(engine)

    # DEV apenas: cria tabelas que NÃO EXISTEM
    if settings.ENV == "dev":
        Base.metadata.create_all(bind=engine)

    # garante admin
    db = SessionLocal()
    try:
        ensure_admin(db)
    finally:
        db.close()
