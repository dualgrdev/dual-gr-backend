from datetime import datetime

from sqlalchemy import DateTime, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AcessoApp(Base):
    __tablename__ = "acessos_app"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    paciente_id: Mapped[int] = mapped_column(Integer, ForeignKey("pacientes.id"), nullable=False)
    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False)

    evento: Mapped[str] = mapped_column(String(50), nullable=False)  # LOGIN, HOME_OPEN, LINK_CLICK...
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
