from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.material import MaterialApoio
from app.services.storage import save_upload_local


router = APIRouter(tags=["Web - Materiais"])


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


@router.get("/admin/materiais", response_class=HTMLResponse)
def materiais_list(request: Request, db: Session = Depends(get_db)):
    guard = require_login(request)
    if guard:
        return guard

    materiais = db.query(MaterialApoio).order_by(MaterialApoio.is_active.desc(), MaterialApoio.id.desc()).all()
    templates = request.app.state.templates
    return templates.TemplateResponse("materiais.html", {"request": request, "materiais": materiais})


@router.post("/admin/materiais/create")
def materiais_create(
    request: Request,
    titulo: str = Form(...),
    descricao: str = Form(None),
    tipo: str = Form(...),  # PDF ou IMG
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    guard = require_login(request)
    if guard:
        return guard

    titulo = (titulo or "").strip()
    descricao = (descricao or "").strip() or None
    tipo = (tipo or "").strip().upper()

    if len(titulo) < 2 or tipo not in ("PDF", "IMG"):
        return RedirectResponse(url="/admin/materiais?msg=invalido", status_code=303)

    try:
        if tipo == "PDF":
            url = save_upload_local(arquivo, subdir="materiais", allowed_exts={".pdf"})
        else:
            url = save_upload_local(arquivo, subdir="materiais", allowed_exts={".jpg", ".jpeg", ".png", ".webp"})
    except Exception:
        return RedirectResponse(url="/admin/materiais?msg=arquivo_invalido", status_code=303)

    m = MaterialApoio(titulo=titulo, descricao=descricao, tipo=tipo, arquivo_url=url, is_active=True)
    db.add(m)
    db.commit()

    return RedirectResponse(url="/admin/materiais?msg=criado", status_code=303)


@router.post("/admin/materiais/toggle")
def materiais_toggle(
    request: Request,
    material_id: int = Form(...),
    db: Session = Depends(get_db),
):
    guard = require_login(request)
    if guard:
        return guard

    m = db.query(MaterialApoio).filter(MaterialApoio.id == material_id).first()
    if not m:
        return RedirectResponse(url="/admin/materiais?msg=nao_encontrado", status_code=303)

    m.is_active = not m.is_active
    db.commit()

    return RedirectResponse(url="/admin/materiais?msg=atualizado", status_code=303)


@router.post("/admin/materiais/delete")
def materiais_delete(
    request: Request,
    material_id: int = Form(...),
    db: Session = Depends(get_db),
):
    guard = require_login(request)
    if guard:
        return guard

    m = db.query(MaterialApoio).filter(MaterialApoio.id == material_id).first()
    if not m:
        return RedirectResponse(url="/admin/materiais?msg=nao_encontrado", status_code=303)

    db.delete(m)
    db.commit()

    return RedirectResponse(url="/admin/materiais?msg=removido", status_code=303)
