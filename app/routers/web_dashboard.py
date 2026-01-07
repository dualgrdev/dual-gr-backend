from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import SessionLocal
from app.models import AcessoApp, Empresa


router = APIRouter(tags=["Web Dashboard"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_login(request: Request):
    if not request.session.get("painel_user_id"):
        return RedirectResponse(url="/admin/login", status_code=303)
    return None


@router.get("/admin", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    guard = require_login(request)
    if guard:
        return guard

    # Períodos (UTC). Depois ajustamos para America/Sao_Paulo se quiser.
    now = datetime.utcnow()
    start_today = datetime(now.year, now.month, now.day)
    start_month = datetime(now.year, now.month, 1)

    # KPIs
    acessos_hoje = (
        db.query(func.count(AcessoApp.id))
        .filter(AcessoApp.created_at >= start_today)
        .scalar()
        or 0
    )

    acessos_mes = (
        db.query(func.count(AcessoApp.id))
        .filter(AcessoApp.created_at >= start_month)
        .scalar()
        or 0
    )

    empresas_total = (
        db.query(func.count(Empresa.id))
        .scalar()
        or 0
    )

    # Top empresas por acessos no mês
    top_empresas = (
        db.query(Empresa.nome, func.count(AcessoApp.id).label("total"))
        .join(AcessoApp, AcessoApp.empresa_id == Empresa.id)
        .filter(AcessoApp.created_at >= start_month)
        .group_by(Empresa.nome)
        .order_by(func.count(AcessoApp.id).desc())
        .limit(10)
        .all()
    )

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "acessos_hoje": acessos_hoje,
            "acessos_mes": acessos_mes,
            "empresas_total": empresas_total,
            "top_empresas": top_empresas,
        },
    )
