from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Paciente
from app.models.anamnese import AnamneseRegistro
from app.schemas.anamnese import AnamneseCreate, AnamneseOut

from jose import jwt, JWTError
from app.core.config import settings


router = APIRouter(prefix="/api/anamnese", tags=["App Anamnese"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_paciente_id_from_token(request: Request) -> int:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token ausente.")
    token = auth.replace("Bearer ", "").strip()

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        sub = payload.get("sub") or ""
        if not str(sub).startswith("paciente:"):
            raise HTTPException(status_code=401, detail="Token inválido.")
        pid = int(str(sub).split("paciente:")[1])
        return pid
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido.")


@router.post("", response_model=AnamneseOut, status_code=201)
def criar_anamnese(data: AnamneseCreate, request: Request, db: Session = Depends(get_db)):
    paciente_id = _get_paciente_id_from_token(request)

    paciente = db.query(Paciente).filter(Paciente.id == paciente_id, Paciente.is_active == True).first()
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")

    reg = AnamneseRegistro(
        paciente_id=paciente.id,
        nome_completo=paciente.nome_completo,
        data_nascimento=data.data_nascimento,
        sexo_biologico=data.sexo_biologico,
        altura_cm=data.altura_cm,
        peso_kg=str(data.peso_kg) if data.peso_kg is not None else None,
        queixa_principal=(data.queixa_principal or "").strip()[:300],
        sintomas=data.sintomas or [],
        sintoma_outro=(data.sintoma_outro or "").strip() or None,
        intensidade_0a10=data.intensidade_0a10,
        frequencia=data.frequencia,
        ha_quanto_tempo=(data.ha_quanto_tempo or "").strip() or None,
        doencas=data.doencas or [],
        doencas_outros=(data.doencas_outros or "").strip() or None,
        usa_medicamento=bool(data.usa_medicamento),
        medicamento_nome=(data.medicamento_nome or "").strip() or None,
        medicamento_dosagem=(data.medicamento_dosagem or "").strip() or None,
        medicamento_frequencia=(data.medicamento_frequencia or "").strip() or None,
        suplementos=data.suplementos or [],
        refeicoes_dia=data.refeicoes_dia,
        consumo_frequente=data.consumo_frequente or [],
        agua_dia=data.agua_dia,
        atividade_fisica=data.atividade_fisica,
        sono_horas=data.sono_horas,
        sono_qualidade=data.sono_qualidade,
        tabagismo=data.tabagismo,
        alcool=data.alcool,
    )

    db.add(reg)
    db.commit()
    db.refresh(reg)

    # converter peso
    out = AnamneseOut.model_validate(reg)
    if reg.peso_kg is not None:
        try:
            out.peso_kg = float(reg.peso_kg)
        except Exception:
            out.peso_kg = None

    return out


@router.get("/last3", response_model=list[AnamneseOut])
def listar_ultimos_3(request: Request, db: Session = Depends(get_db)):
    paciente_id = _get_paciente_id_from_token(request)

    rows = (
        db.query(AnamneseRegistro)
        .filter(AnamneseRegistro.paciente_id == paciente_id)
        .order_by(AnamneseRegistro.id.desc())
        .limit(3)
        .all()
    )

    out_list: list[AnamneseOut] = []
    for r in rows:
        out = AnamneseOut.model_validate(r)
        if r.peso_kg is not None:
            try:
                out.peso_kg = float(r.peso_kg)
            except Exception:
                out.peso_kg = None
        out_list.append(out)
    return out_list
