# app/services/cpf.py
import re
import unicodedata

MAX_BCRYPT_PASSWORD_LEN = 72


def only_digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")


def normalize_text(s: str) -> str:
    """Remove acentos, baixa case, normaliza espaços."""
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_name(s: str) -> str:
    """Normaliza nome (mantém maiúsculas/minúsculas mais amigável)."""
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s


def validate_cpf(cpf: str) -> bool:
    cpf = only_digits(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    def calc_digit(base: str, weights: list[int]) -> str:
        total = sum(int(d) * w for d, w in zip(base, weights))
        r = total % 11
        return "0" if r < 2 else str(11 - r)

    d1 = calc_digit(cpf[:9], list(range(10, 1, -1)))
    d2 = calc_digit(cpf[:9] + d1, list(range(11, 1, -1)))
    return cpf[-2:] == d1 + d2


def validate_cep(cep: str) -> bool:
    cep = only_digits(cep)
    return len(cep) == 8


def validate_phone_br(phone: str) -> bool:
    phone = only_digits(phone)
    # Aceita 10 ou 11 dígitos (com DDD)
    return len(phone) in (10, 11)


def is_strong_password(pw: str) -> bool:
    """
    Regras:
    - mínimo 8 caracteres
    - máximo 72 caracteres (bcrypt limita 72 bytes; limitar por caracteres evita 500)
    - precisa ter pelo menos 1 letra e 1 número
    """
    pw = pw or ""
    if len(pw) < 8:
        return False
    if len(pw) > MAX_BCRYPT_PASSWORD_LEN:
        return False
    has_letter = any(c.isalpha() for c in pw)
    has_digit = any(c.isdigit() for c in pw)
    return has_letter and has_digit
