from io import BytesIO

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.campanha import Campanha
from app.services.storage import save_upload_local

# Pillow (PIL) para validar dimensões
from PIL import Image, UnidentifiedImageError


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


# ============================================================
# Regras de imagem (banner)
# App mostra em 16:9 -> validação aqui evita distorção/corte ruim
# ============================================================
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

MIN_W = 800
MIN_H = 450

MAX_W = 3000
MAX_H = 3000

# tolerância de proporção (w/h)
MIN_AR = 1.60  # ~ (16/10)
MAX_AR = 1.90  # ~ (19/10) - cobre 16:9 com folga pequena


def _get_image_size_and_validate(upload: UploadFile) -> tuple[int, int]:
    """
    Lê o header da imagem e valida:
    - é imagem real
    - dimensões mín/máx
    - proporção compatível com 16:9
    Mantém compatibilidade com save_upload_local (faz seek(0) no final).
    """
    # Lê bytes (precisamos abrir a imagem). Depois damos seek(0) para permitir o salvamento.
    try:
        raw = upload.file.read()
        if not raw:
            raise ValueError("arquivo_vazio")

        img = Image.open(BytesIO(raw))
        img.verify()  # verifica integridade sem decodificar tudo

        # reabrir para pegar size (verify fecha internals)
        img2 = Image.open(BytesIO(raw))
        w, h = img2.size

    except UnidentifiedImageError:
        raise ValueError("img_invalida")
    except Exception:
        # Qualquer falha de leitura
        raise ValueError("img_invalida")
    finally:
        try:
            upload.file.seek(0)
        except Exception:
            pass

    # dimensões
    if w < MIN_W or h < MIN_H:
        raise ValueError("img_pequena")

    if w > MAX_W or h > MAX_H:
        raise ValueError("img_grande")

    # proporção
    ar = (w / h) if h else 0.0
    if ar < MIN_AR or ar > MAX_AR:
        raise ValueError("img_proporcao")

    return w, h


@router.get("/admin/campanhas", response_class=HTMLResponse)
def campanhas_list(request: Request, db: Session = Depends(get_db)):
    guard = require_login(request)
    if guard:
        return guard

    campanhas = (
        db.query(Campanha)
        .order_by(Campanha.is_active.desc(), Campanha.ordem.asc(), Campanha.id.desc())
        .all()
    )
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
            # 1) valida dimensões e proporção (sem quebrar save_upload_local)
            _get_image_size_and_validate(imagem)

            # 2) salva no storage
            imagem_url = save_upload_local(
                imagem,
                subdir="campanhas",
                allowed_exts=ALLOWED_EXTS,
            )
        except ValueError as e:
            code = str(e)

            # mapeia para msgs do painel (você pode tratar no template)
            if code == "img_pequena":
                return RedirectResponse(url="/admin/campanhas?msg=img_pequena", status_code=303)
            if code == "img_grande":
                return RedirectResponse(url="/admin/campanhas?msg=img_grande", status_code=303)
            if code == "img_proporcao":
                return RedirectResponse(url="/admin/campanhas?msg=img_proporcao", status_code=303)

            return RedirectResponse(url="/admin/campanhas?msg=img_invalida", status_code=303)
        except Exception:
            return RedirectResponse(url="/admin/campanhas?msg=img_invalida", status_code=303)

    c = Campanha(
        titulo=titulo,
        mensagem=mensagem,
        imagem_url=imagem_url,
        ordem=ordem,
        is_active=True,
    )
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
