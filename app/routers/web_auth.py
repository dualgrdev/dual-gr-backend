from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.db.session import SessionLocal
from app.models.painel_user import PainelUser
from app.services.cpf import only_digits

router = APIRouter(tags=["Web Auth"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_templates(request: Request):
    return request.app.state.templates


@router.get("/admin/login", response_class=HTMLResponse)
def admin_login_get(request: Request):
    templates = get_templates(request)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/admin/login")
def admin_login_post(
    request: Request,
    cpf: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db),
):
    cpf_d = only_digits(cpf)
    user = db.query(PainelUser).filter(PainelUser.cpf == cpf_d, PainelUser.is_active == True).first()

    if not user or not verify_password(senha, user.password_hash):
        templates = get_templates(request)
        return templates.TemplateResponse("login.html", {"request": request, "error": "CPF ou senha inválidos."})

    request.session["painel_user_id"] = user.id

    if user.must_change_password:
        return RedirectResponse(url="/admin/change-password", status_code=303)

    return RedirectResponse(url="/admin", status_code=303)


@router.get("/admin/change-password", response_class=HTMLResponse)
def change_password_get(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("painel_user_id")
    if not user_id:
        return RedirectResponse(url="/admin/login", status_code=303)

    templates = get_templates(request)
    return templates.TemplateResponse("change_password.html", {"request": request, "error": None})


@router.post("/admin/change-password")
def change_password_post(
    request: Request,
    nova_senha: str = Form(...),
    repetir_senha: str = Form(...),
    db: Session = Depends(get_db),
):
    user_id = request.session.get("painel_user_id")
    if not user_id:
        return RedirectResponse(url="/admin/login", status_code=303)

    user = db.query(PainelUser).filter(PainelUser.id == user_id, PainelUser.is_active == True).first()
    if not user:
        request.session.clear()
        return RedirectResponse(url="/admin/login", status_code=303)

    if nova_senha != repetir_senha:
        templates = get_templates(request)
        return templates.TemplateResponse(
            "change_password.html", {"request": request, "error": "Senha e repetir senha não conferem."}
        )

    user.password_hash = hash_password(nova_senha)
    user.must_change_password = False
    db.commit()

    return RedirectResponse(url="/admin", status_code=303)


@router.get("/admin/logout")
def admin_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=303)
