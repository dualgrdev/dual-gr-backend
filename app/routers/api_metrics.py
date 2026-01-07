from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import AcessoApp, Paciente


router = APIRouter(prefix="/api/metrics", tags=["Metrics (App)"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


Evento = Literal[
    "LOGIN",
    "HOME_OPEN",
    "LINK_CLICK_PERFIL",
    "LINK_CLICK_RECEITAS",
    "LINK_CLICK_URGENCIA",
    "WHATSAPP_CLICK",
]


class MetricIn(BaseModel):
    cpf: str = Field(min_length=11, max_length=14)
    evento: Evento
    meta: Optional[str] = None  # reservado para futuro (ex.: tela, versão app etc)


def only_digits(s: str) -> str:
    import re
    return re.sub(r"\D+", "", s or "")


@router.post("/event", response_model=dict)
def post_event(payload: MetricIn, db: Session = Depends(get_db)):
    cpf = only_digits(payload.cpf)

    paciente = db.query(Paciente).filter(Paciente.cpf == cpf, Paciente.is_active == True).first()
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")

    evento = AcessoApp(
        paciente_id=paciente.id,
        empresa_id=paciente.empresa_id,
        evento=payload.evento,
        created_at=datetime.utcnow(),
    )
    db.add(evento)
    db.commit()

    return {"success": True}
