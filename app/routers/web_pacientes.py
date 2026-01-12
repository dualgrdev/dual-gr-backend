from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import SessionLocal
from app.models.paciente import Paciente
from app.models.empresa import Empresa

router = APIRouter(prefix="/admin/pacientes", tags=["Web - Pacientes"])


# =========================
# DB
# =========================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================
# Guard: painel
# =========================
def require_admin_login(request: Request):
    user_id = request.session.get("painel_user_id")
    if not user_id:
        return RedirectResponse(url="/admin/login", status_code=303)
    return None


# =========================
# Helpers
# =========================
def only_digits(s: str) -> str:
    return re.sub(r"\D+", "", (s or ""))


# =========================
# LISTAR PACIENTES (com filtros)
# =========================
@router.get("/", response_class=HTMLResponse)
def pacientes_list(
    request: Request,
    db: Session = Depends(get_db),
    cpf: str = "",
    empresa_id: str = "",
    q: str = "",
    page: int = 1,
    page_size: int = 20,
):
    redir = require_admin_login(request)
    if redir:
        return redir

    templates = request.app.state.templates

    # paginação segura
    try:
        page = int(page or 1)
    except Exception:
        page = 1
    page = max(page, 1)

    try:
        page_size = int(page_size or 20)
    except Exception:
        page_size = 20
    page_size = 20 if page_size not in (10, 20, 50, 100) else page_size

    cpf_digits = only_digits(cpf)

    empresa_id_int: Optional[int] = None
    if str(empresa_id).strip().isdigit():
        empresa_id_int = int(str(empresa_id).strip())

    q_clean = (q or "").strip()

    # dropdown empresas
    empresas = (
        db.query(Empresa)
        .filter(Empresa.is_active == True)
        .order_by(Empresa.nome.asc())
        .all()
    )

    query = (
        db.query(Paciente, Empresa)
        .join(Empresa, Paciente.empresa_id == Empresa.id)
        .filter(Paciente.is_active == True)
    )

    if cpf_digits:
        query = query.filter(Paciente.cpf == cpf_digits)

    if empresa_id_int:
        query = query.filter(Paciente.empresa_id == empresa_id_int)

    if q_clean:
        q_like = f"%{q_clean.lower()}%"
        query = query.filter(func.lower(Paciente.nome_completo).like(q_like))

    total = query.count()

    rows = (
        query.order_by(Paciente.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    pacientes_view = []
    for p, e in rows:
        pacientes_view.append(
            {
                "id": p.id,
                "nome_completo": p.nome_completo,
                "cpf": p.cpf,
                "celular": p.celular,
                "empresa_id": p.empresa_id,
                "empresa_nome": e.nome if e else "",

                # Perfil Saúde (novos campos)
                "data_nascimento": getattr(p, "data_nascimento", None),
                "sexo_biologico": getattr(p, "sexo_biologico", None),
                "altura_cm": getattr(p, "altura_cm", None),
                "peso_kg": getattr(p, "peso_kg", None),

                "created_at": p.created_at,
                "last_login_at": p.last_login_at,
            }
        )

    pages = max((total + page_size - 1) // page_size, 1)

    return templates.TemplateResponse(
        "pacientes/list.html",
        {
            "request": request,
            "pacientes": pacientes_view,
            "empresas": empresas,
            "filters": {
                "cpf": cpf_digits,
                "empresa_id": empresa_id_int or "",
                "q": q_clean,
            },
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": pages,
                "has_prev": page > 1,
                "has_next": page < pages,
                "prev_page": page - 1,
                "next_page": page + 1,
            },
        },
    )


# =========================
# DETALHE DO PACIENTE
# =========================
@router.get("/{paciente_id}", response_class=HTMLResponse)
def paciente_detail(
    request: Request,
    paciente_id: int,
    db: Session = Depends(get_db),
):
    redir = require_admin_login(request)
    if redir:
        return redir

    templates = request.app.state.templates

    row = (
        db.query(Paciente, Empresa)
        .join(Empresa, Paciente.empresa_id == Empresa.id)
        .filter(Paciente.id == paciente_id, Paciente.is_active == True)
        .first()
    )
    if not row:
        return RedirectResponse(url="/admin/pacientes", status_code=303)

    p, e = row

    paciente = {
        "id": p.id,
        "nome_completo": p.nome_completo,
        "cpf": p.cpf,
        "celular": p.celular,
        "empresa_nome": e.nome if e else "",
        "endereco": p.endereco,
        "cep": p.cep,
        "created_at": p.created_at,
        "last_login_at": p.last_login_at,

        # Perfil Saúde
        "data_nascimento": getattr(p, "data_nascimento", None),
        "sexo_biologico": getattr(p, "sexo_biologico", None),
        "altura_cm": getattr(p, "altura_cm", None),
        "peso_kg": getattr(p, "peso_kg", None),
    }

    return templates.TemplateResponse(
        "pacientes/detail.html",
        {
            "request": request,
            "paciente": paciente,
        },
    )
