from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Empresa, Campanha, MaterialApoio


router = APIRouter(prefix="/api/public", tags=["Public (App)"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/empresas")
def listar_empresas(db: Session = Depends(get_db)):
    empresas = (
        db.query(Empresa)
        .filter(Empresa.is_active == True)
        .order_by(Empresa.nome.asc())
        .all()
    )
    return [{"id": e.id, "nome": e.nome} for e in empresas]


@router.get("/campanhas")
def listar_campanhas(db: Session = Depends(get_db)):
    campanhas = (
        db.query(Campanha)
        .filter(Campanha.is_active == True)
        .order_by(Campanha.ordem.asc(), Campanha.id.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "titulo": c.titulo,
            "mensagem": c.mensagem,
            "imagem_url": c.imagem_url,
            "ordem": c.ordem,
        }
        for c in campanhas
    ]


@router.get("/materiais")
def listar_materiais(db: Session = Depends(get_db)):
    materiais = (
        db.query(MaterialApoio)
        .filter(MaterialApoio.is_active == True)
        .order_by(MaterialApoio.id.desc())
        .all()
    )
    return [
        {
            "id": m.id,
            "titulo": m.titulo,
            "descricao": m.descricao,
            "tipo": m.tipo,
            "arquivo_url": m.arquivo_url,
        }
        for m in materiais
    ]
