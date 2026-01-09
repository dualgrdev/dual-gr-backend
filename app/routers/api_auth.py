from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    hash_password,
    normalize_text,
    verify_password,
)
from app.db.session import SessionLocal
from app.models import Empresa, Paciente
from app.schemas.auth import (
    ForgotQuestionOut,
    ForgotVerifyIn,
    LoginIn,
    ResetPasswordIn,
    TokenOut,
)
from app.schemas.paciente import PacienteCreate
from app.services.cpf import (
    only_digits,
    validate_cpf,
    validate_cep,
    validate_phone_br,
    is_strong_password,
)

router = APIRouter(prefix="/api/auth", tags=["App Auth"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/register", response_model=dict)
def register(data: PacienteCreate, db: Session = Depends(get_db)):
    cpf = only_digits(data.cpf)
    celular = only_digits(data.celular)
    cep = only_digits(data.cep)

    if not validate_cpf(cpf):
        raise HTTPException(status_code=400, detail="CPF inválido.")
    if not validate_phone_br(celular):
        raise HTTPException(status_code=400, detail="Celular inválido.")
    if not validate_cep(cep):
        raise HTTPException(status_code=400, detail="CEP inválido.")

    if data.senha != data.repetir_senha:
        raise HTTPException(status_code=400, detail="Senha e repetir senha não conferem.")
    if not is_strong_password(data.senha):
        raise HTTPException(
            status_code=400,
            detail="Senha fraca. Use mínimo 8 caracteres, com letras e números.",
        )

    # ============================================================
    # Empresa deve existir e estar ativa
    # Preferencial: empresa_id (vem do dropdown do app)
    # Fallback: empresa por nome (compatibilidade)
    # ============================================================
    empresa = None

    if data.empresa_id:
        empresa = (
            db.query(Empresa)
            .filter(Empresa.id == data.empresa_id, Empresa.is_active == True)
            .first()
        )
    else:
        nome_emp = (data.empresa or "").strip()
        if nome_emp:
            empresa = (
                db.query(Empresa)
                .filter(Empresa.nome == nome_emp, Empresa.is_active == True)
                .first()
            )

    if not empresa:
        raise HTTPException(status_code=400, detail="Empresa não autorizada ou não cadastrada.")

    exists = db.query(Paciente).filter(Paciente.cpf == cpf).first()
    if exists:
        raise HTTPException(status_code=409, detail="CPF já cadastrado.")

    # bcrypt limite 72 bytes: hash_password() pode levantar ValueError agora
    try:
        pw_hash = hash_password(data.senha)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        # fallback defensivo: não vaza erro interno
        raise HTTPException(status_code=400, detail="Senha inválida.")

    paciente = Paciente(
        nome_completo=(data.nome_completo or "").strip(),
        cpf=cpf,
        celular=celular,
        empresa_id=empresa.id,
        endereco=(data.endereco or "").strip(),
        cep=cep,
        password_hash=pw_hash,
        pergunta_seg=(data.pergunta_seg or "").strip(),
        resposta_seg_norm=normalize_text(data.resposta_seg),
        is_active=True,
    )
    db.add(paciente)
    db.commit()

    return {"success": True, "message": "Cadastro realizado com sucesso."}


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    cpf = only_digits(data.cpf)
    user = db.query(Paciente).filter(Paciente.cpf == cpf, Paciente.is_active == True).first()

    # Nunca deixar bcrypt/passlib derrubar com 500
    ok = False
    try:
        ok = bool(user) and verify_password(data.senha, user.password_hash)
    except Exception:
        ok = False

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="CPF ou senha inválidos.",
        )

    user.last_login_at = datetime.utcnow()
    db.commit()

    token = create_access_token(subject=f"paciente:{user.id}")
    return TokenOut(access_token=token)


@router.get("/forgot/question", response_model=ForgotQuestionOut)
def forgot_question(cpf: str, db: Session = Depends(get_db)):
    cpf_d = only_digits(cpf)
    user = db.query(Paciente).filter(Paciente.cpf == cpf_d, Paciente.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return ForgotQuestionOut(pergunta=user.pergunta_seg)


@router.post("/forgot/verify", response_model=dict)
def forgot_verify(data: ForgotVerifyIn, db: Session = Depends(get_db)):
    cpf = only_digits(data.cpf)
    user = db.query(Paciente).filter(Paciente.cpf == cpf, Paciente.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    if normalize_text(data.resposta) != user.resposta_seg_norm:
        raise HTTPException(status_code=400, detail="Resposta incorreta.")

    return {"success": True, "message": "Resposta confirmada."}


@router.post("/forgot/reset", response_model=dict)
def forgot_reset(data: ResetPasswordIn, db: Session = Depends(get_db)):
    cpf = only_digits(data.cpf)
    user = db.query(Paciente).filter(Paciente.cpf == cpf, Paciente.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    if normalize_text(data.resposta) != user.resposta_seg_norm:
        raise HTTPException(status_code=400, detail="Resposta incorreta.")

    if data.nova_senha != data.repetir_senha:
        raise HTTPException(status_code=400, detail="Senha e repetir senha não conferem.")
    if not is_strong_password(data.nova_senha):
        raise HTTPException(
            status_code=400,
            detail="Senha fraca. Use mínimo 8 caracteres, com letras e números.",
        )

    try:
        user.password_hash = hash_password(data.nova_senha)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=400, detail="Senha inválida.")

    db.commit()

    return {"success": True, "message": "Senha alterada com sucesso."}
