# app/routers/api_auth.py
from __future__ import annotations

from datetime import datetime
from hmac import compare_digest

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
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
    ChangePasswordIn,  # ✅ novo
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

security = HTTPBearer(auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# Helpers
# ============================================================
def _get_active_user_by_cpf(db: Session, cpf_raw: str) -> Paciente:
    cpf = only_digits(cpf_raw)
    user = db.query(Paciente).filter(Paciente.cpf == cpf, Paciente.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return user


def _check_security_answer(user: Paciente, answer_raw: str) -> None:
    expected = (user.resposta_seg_norm or "").strip()
    given = normalize_text(answer_raw or "")
    if not expected or not compare_digest(given, expected):
        raise HTTPException(status_code=400, detail="Resposta incorreta.")


def _parse_subject(sub: str) -> int:
    """
    subject esperado: "paciente:{id}"
    """
    s = (sub or "").strip()
    if not s.startswith("paciente:"):
        raise HTTPException(status_code=401, detail="Token inválido (subject).")
    try:
        return int(s.split(":", 1)[1])
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido (subject).")


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.")


def get_current_paciente(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Paciente:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="Não autenticado.")
    payload = _decode_token(creds.credentials)
    paciente_id = _parse_subject(payload.get("sub", ""))

    user = db.query(Paciente).filter(Paciente.id == paciente_id, Paciente.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado ou inativo.")
    return user


# ============================================================
# REGISTER
# ============================================================
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

    # Empresa ativa (preferencial por id)
    empresa = None
    if data.empresa_id:
        empresa = db.query(Empresa).filter(Empresa.id == data.empresa_id, Empresa.is_active == True).first()
    else:
        nome_emp = (data.empresa or "").strip()
        if nome_emp:
            empresa = db.query(Empresa).filter(Empresa.nome == nome_emp, Empresa.is_active == True).first()

    if not empresa:
        raise HTTPException(status_code=400, detail="Empresa não autorizada ou não cadastrada.")

    exists = db.query(Paciente).filter(Paciente.cpf == cpf).first()
    if exists:
        raise HTTPException(status_code=409, detail="CPF já cadastrado.")

    try:
        pw_hash = hash_password(data.senha)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
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


# ============================================================
# LOGIN
# ============================================================
@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    cpf = only_digits(data.cpf)
    user = db.query(Paciente).filter(Paciente.cpf == cpf, Paciente.is_active == True).first()

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

    return TokenOut(
        access_token=token,
        paciente_id=user.id,
        nome_completo=user.nome_completo,
        cpf=user.cpf,
    )


# ============================================================
# CHANGE PASSWORD (✅ NOVO - via Bearer token)
# ============================================================
@router.post("/change-password", response_model=dict)
def change_password(
    data: ChangePasswordIn,
    user: Paciente = Depends(get_current_paciente),
    db: Session = Depends(get_db),
):
    # valida repetir
    if data.nova_senha != data.repetir_senha:
        raise HTTPException(status_code=400, detail="Nova senha e repetir senha não conferem.")

    # valida força
    if not is_strong_password(data.nova_senha):
        raise HTTPException(
            status_code=400,
            detail="Senha fraca. Use mínimo 8 caracteres, com letras e números.",
        )

    # valida senha atual
    try:
        if not verify_password(data.senha_atual, user.password_hash):
            raise HTTPException(status_code=400, detail="Senha atual incorreta.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")

    # atualiza hash
    try:
        user.password_hash = hash_password(data.nova_senha)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=400, detail="Senha inválida.")

    db.commit()
    return {"success": True, "message": "Senha alterada com sucesso."}


# ============================================================
# ME (compatibilidade)
# ============================================================
@router.get("/me", response_model=dict)
def me(cpf: str, db: Session = Depends(get_db)):
    user = _get_active_user_by_cpf(db, cpf)
    return {
        "id": user.id,
        "nome_completo": user.nome_completo,
        "cpf": user.cpf,
        "celular": user.celular,
        "empresa_id": user.empresa_id,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


# ============================================================
# FORGOT FLOW
# ============================================================
@router.get("/forgot/question", response_model=ForgotQuestionOut)
def forgot_question(cpf: str, db: Session = Depends(get_db)):
    user = _get_active_user_by_cpf(db, cpf)
    return ForgotQuestionOut(pergunta=user.pergunta_seg or "")


@router.post("/forgot/verify", response_model=dict)
def forgot_verify(data: ForgotVerifyIn, db: Session = Depends(get_db)):
    user = _get_active_user_by_cpf(db, data.cpf)
    _check_security_answer(user, data.resposta)
    return {"success": True, "message": "Resposta confirmada."}


@router.post("/forgot/reset", response_model=dict)
def forgot_reset(data: ResetPasswordIn, db: Session = Depends(get_db)):
    user = _get_active_user_by_cpf(db, data.cpf)
    _check_security_answer(user, data.resposta)

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
