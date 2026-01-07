from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.campanha import Campanha
from app.services.storage import save_upload_local


router = APIRouter(tags=["Web - Campanhas"])


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


@router.get("/admin/campanhas", response_class=HTMLResponse)
def campanhas_list(request: Request, db: Session = Depends(get_db)):
    guard = require_login(request)
    if guard:
        return guard

    campanhas = db.query(Campanha).order_by(Campanha.is_active.desc(), Campanha.ordem.asc(), Campanha.id.desc()).all()
    templates = request.app.state.templates
    return templates.TemplateResponse("campanhas.html", {"request": request, "campanhas": campanhas})


@router.post("/admin/campanhas/create")
def campanhas_create(
    request: Request,
    titulo: str = Form(...),
    mensagem: str = Form(...),
    ordem: int = Form(0),
    imagem: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    guard = require_login(request)
    if guard:
        return guard

    titulo = (titulo or "").strip()
    mensagem = (mensagem or "").strip()
    if len(titulo) < 2 or len(mensagem) < 3:
        return RedirectResponse(url="/admin/campanhas?msg=invalido", status_code=303)

    imagem_url = None
    if imagem and imagem.filename:
        try:
            imagem_url = save_upload_local(imagem, subdir="campanhas", allowed_exts={".jpg", ".jpeg", ".png", ".webp"})
        except Exception:
            return RedirectResponse(url="/admin/campanhas?msg=img_invalida", status_code=303)

    c = Campanha(titulo=titulo, mensagem=mensagem, imagem_url=imagem_url, ordem=ordem, is_active=True)
    db.add(c)
    db.commit()

    return RedirectResponse(url="/admin/campanhas?msg=criada", status_code=303)


@router.post("/admin/campanhas/toggle")
def campanhas_toggle(
    request: Request,
    campanha_id: int = Form(...),
    db: Session = Depends(get_db),
):
    guard = require_login(request)
    if guard:
        return guard

    c = db.query(Campanha).filter(Campanha.id == campanha_id).first()
    if not c:
        return RedirectResponse(url="/admin/campanhas?msg=nao_encontrada", status_code=303)

    c.is_active = not c.is_active
    db.commit()
    return RedirectResponse(url="/admin/campanhas?msg=atualizada", status_code=303)


@router.post("/admin/campanhas/delete")
def campanhas_delete(
    request: Request,
    campanha_id: int = Form(...),
    db: Session = Depends(get_db),
):
    guard = require_login(request)
    if guard:
        return guard

    c = db.query(Campanha).filter(Campanha.id == campanha_id).first()
    if not c:
        return RedirectResponse(url="/admin/campanhas?msg=nao_encontrada", status_code=303)

    db.delete(c)
    db.commit()
    return RedirectResponse(url="/admin/campanhas?msg=removida", status_code=303)
