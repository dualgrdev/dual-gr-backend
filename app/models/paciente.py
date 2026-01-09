from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Paciente(Base):
    __tablename__ = "pacientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    nome_completo: Mapped[str] = mapped_column(String(200), nullable=False)
    cpf: Mapped[str] = mapped_column(String(11), unique=True, index=True, nullable=False)
    celular: Mapped[str] = mapped_column(String(11), nullable=False)

    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False)
    empresa = relationship("Empresa")

    endereco: Mapped[str] = mapped_column(String(250), nullable=False)
    cep: Mapped[str] = mapped_column(String(8), nullable=False)

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    pergunta_seg: Mapped[str] = mapped_column(String(200), nullable=False)
    resposta_seg_norm: Mapped[str] = mapped_column(String(200), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
