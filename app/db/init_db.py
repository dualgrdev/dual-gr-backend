from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.painel_user import PainelUser


DEFAULT_ADMIN_CPF = "27080591813"
DEFAULT_ADMIN_PASSWORD = "123456"


def ensure_admin(db: Session) -> None:
    admin = db.query(PainelUser).filter(PainelUser.cpf == DEFAULT_ADMIN_CPF).first()
    if admin:
        return

    admin = PainelUser(
        cpf=DEFAULT_ADMIN_CPF,
        email="admin@dualsaude.local",
        password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
        role="ADMIN",
        must_change_password=True,
        is_active=True,
    )
    db.add(admin)
    db.commit()
