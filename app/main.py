# app/main.py
from pathlib import Path

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

from app.routers.web_auth import router as web_auth_router
from app.routers.web_dashboard import router as web_dashboard_router
from app.routers.web_empresas import router as web_empresas_router
from app.routers.web_campanhas import router as web_campanhas_router
from app.routers.web_materiais import router as web_materiais_router

from app.routers.fin_auth import router as fin_auth_router
from app.routers.fin_caixa import router as fin_caixa_router
from app.routers.fin_relatorios import router as fin_relatorios_router


app = FastAPI(title=settings.APP_NAME)

# CORS (necessário para consumo pelo app e futuras integrações)
# Em produção você pode restringir allow_origins para o domínio do app/painel.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sessão para painel web (cookie)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# Templates + Static
templates = Jinja2Templates(directory="app/templates")
app.state.templates = templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Storage local (DEV): garante pasta e expõe via /uploads
storage_dir = ensure_storage_dir()
app.mount("/uploads", StaticFiles(directory=str(Path(storage_dir))), name="uploads")

# Routers (API App)
app.include_router(api_auth_router)
app.include_router(api_public_router)
app.include_router(api_metrics_router)

# Routers (Web Admin)
app.include_router(web_auth_router)
app.include_router(web_dashboard_router)
app.include_router(web_empresas_router)
app.include_router(web_campanhas_router)
app.include_router(web_materiais_router)

# Routers (Financeiro)
app.include_router(fin_auth_router)
app.include_router(fin_caixa_router)
app.include_router(fin_relatorios_router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}


@app.on_event("startup")
def on_startup():
    # garante pasta storage (uploads)
    ensure_storage_dir()

    # DEV: cria tabelas automaticamente (evita travar antes do Alembic).
    # Produção (Render/Postgres): usaremos Alembic.
    if settings.ENV == "dev":
        Base.metadata.create_all(bind=engine)

    # Seed do admin (se não existir)
    db = SessionLocal()
    try:
        ensure_admin(db)
    finally:
        db.close()
