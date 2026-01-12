import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt limita o segredo a 72 bytes
_BCRYPT_MAX_BYTES = 72


def _password_too_long(password: str) -> bool:
    try:
        return len((password or "").encode("utf-8")) > _BCRYPT_MAX_BYTES
    except Exception:
        # se der qualquer problema, trata como inválido
        return True


def hash_password(password: str) -> str:
    if _password_too_long(password):
        raise ValueError("Senha muito longa para bcrypt (máx. 72 bytes).")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Evita crash do passlib/bcrypt quando a senha excede 72 bytes
    if _password_too_long(plain_password):
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(
    subject: str,
    expires_minutes: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    now = datetime.now(timezone.utc)
    minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    exp = now + timedelta(minutes=minutes)

    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    if extra:
        payload.update(extra)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def normalize_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\s+", " ", s)
    return s
