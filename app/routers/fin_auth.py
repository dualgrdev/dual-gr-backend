from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.security import verify_password, hash_password
from app.services.cpf import only_digits

# Import do modelo do usuário do painel (tentativas compatíveis)
try:
    from app.models import Usuario as AdminUser  # caso seu projeto use Usuario
except Exception:
    try:
        from app.models import PainelUser as AdminUser  # caso use PainelUser
    except Exception:
        AdminUser = None  # vai falhar de forma clara se não existir


router = APIRouter(tags=["Financeiro - Auth"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_finance_login(request: Request):
    if not request.session.get("finance_user_id"):
        return RedirectResponse(url="/financeiro/login", status_code=303)
    return None


@router.get("/financeiro/login", response_class=HTMLResponse)
def financeiro_login_get(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse("financeiro/login.html", {"request": request, "error": None})


@router.post("/financeiro/login")
def financeiro_login_post(
    request: Request,
    cpf: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates

    if AdminUser is None:
        return templates.TemplateResponse(
            "financeiro/login.html",
            {"request": request, "error": "Modelo de usuário do painel não encontrado (AdminUser)."},
        )

    cpf_d = only_digits(cpf)

    # Campos esperados: cpf, password_hash, is_active
    user = db.query(AdminUser).filter(AdminUser.cpf == cpf_d, AdminUser.is_active == True).first()
    if not user or not verify_password(senha, user.password_hash):
        return templates.TemplateResponse(
            "financeiro/login.html",
            {"request": request, "error": "CPF ou senha inválidos."},
        )

    request.session["finance_user_id"] = user.id

    # Se ainda estiver na senha padrão 123456, força troca (sem precisar de coluna extra)
    if verify_password("123456", user.password_hash):
        return RedirectResponse(url="/financeiro/change-password", status_code=303)

    return RedirectResponse(url="/financeiro/dashboard", status_code=303)


@router.get("/financeiro/change-password", response_class=HTMLResponse)
def financeiro_change_password_get(request: Request):
    guard = require_finance_login(request)
    if guard:
        return guard
    templates = request.app.state.templates
    return templates.TemplateResponse("financeiro/change_password.html", {"request": request, "error": None})


@router.post("/financeiro/change-password")
def financeiro_change_password_post(
    request: Request,
    nova_senha: str = Form(...),
    repetir_senha: str = Form(...),
    db: Session = Depends(get_db),
):
    guard = require_finance_login(request)
    if guard:
        return guard

    templates = request.app.state.templates

    if nova_senha != repetir_senha:
        return templates.TemplateResponse(
            "financeiro/change_password.html",
            {"request": request, "error": "Senha e repetir senha não conferem."},
        )

    if AdminUser is None:
        return templates.TemplateResponse(
            "financeiro/change_password.html",
            {"request": request, "error": "Modelo de usuário do painel não encontrado (AdminUser)."},
        )

    user_id = request.session.get("finance_user_id")
    user = db.query(AdminUser).filter(AdminUser.id == user_id, AdminUser.is_active == True).first()
    if not user:
        request.session.pop("finance_user_id", None)
        return RedirectResponse(url="/financeiro/login", status_code=303)

    user.password_hash = hash_password(nova_senha)
    db.commit()

    return RedirectResponse(url="/financeiro/dashboard", status_code=303)


@router.get("/financeiro/logout")
def financeiro_logout(request: Request):
    request.session.pop("finance_user_id", None)
    return RedirectResponse(url="/financeiro/login", status_code=303)
