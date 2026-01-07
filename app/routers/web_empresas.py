from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.empresa import Empresa


router = APIRouter(tags=["Web - Empresas"])


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


@router.get("/admin/empresas", response_class=HTMLResponse)
def empresas_list(request: Request, db: Session = Depends(get_db)):
    guard = require_login(request)
    if guard:
        return guard

    empresas = db.query(Empresa).order_by(Empresa.is_active.desc(), Empresa.nome.asc()).all()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "empresas.html",
        {"request": request, "empresas": empresas, "error": None, "success": None},
    )


@router.post("/admin/empresas/create")
def empresas_create(
    request: Request,
    nome: str = Form(...),
    cnpj: str = Form(None),
    db: Session = Depends(get_db),
):
    guard = require_login(request)
    if guard:
        return guard

    nome = (nome or "").strip()
    cnpj = (cnpj or "").strip() or None

    if len(nome) < 2:
        return RedirectResponse(url="/admin/empresas?msg=nome_invalido", status_code=303)

    # Impede duplicidade por nome
    exists = db.query(Empresa).filter(Empresa.nome == nome).first()
    if exists:
        return RedirectResponse(url="/admin/empresas?msg=duplicada", status_code=303)

    emp = Empresa(nome=nome, cnpj=cnpj, is_active=True)
    db.add(emp)
    db.commit()

    return RedirectResponse(url="/admin/empresas?msg=criada", status_code=303)


@router.post("/admin/empresas/toggle")
def empresas_toggle(
    request: Request,
    empresa_id: int = Form(...),
    db: Session = Depends(get_db),
):
    guard = require_login(request)
    if guard:
        return guard

    emp = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not emp:
        return RedirectResponse(url="/admin/empresas?msg=nao_encontrada", status_code=303)

    emp.is_active = not emp.is_active
    db.commit()

    return RedirectResponse(url="/admin/empresas?msg=atualizada", status_code=303)


@router.post("/admin/empresas/delete")
def empresas_delete(
    request: Request,
    empresa_id: int = Form(...),
    db: Session = Depends(get_db),
):
    guard = require_login(request)
    if guard:
        return guard

    emp = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not emp:
        return RedirectResponse(url="/admin/empresas?msg=nao_encontrada", status_code=303)

    db.delete(emp)
    db.commit()

    return RedirectResponse(url="/admin/empresas?msg=removida", status_code=303)
