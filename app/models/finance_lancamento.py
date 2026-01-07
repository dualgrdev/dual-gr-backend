from datetime import datetime, date
from sqlalchemy import Date, DateTime, Integer, String, Boolean, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FinanceLancamento(Base):
    __tablename__ = "finance_lancamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ENTRADA / SAIDA
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)

    # PAGO / PENDENTE
    status: Mapped[str] = mapped_column(String(10), default="PAGO", nullable=False)

    data: Mapped[date] = mapped_column(Date, nullable=False)
    valor: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    descricao: Mapped[str] = mapped_column(String(240), nullable=False)

    categoria_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("finance_categorias.id"), nullable=True)
    forma_pagamento_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("finance_formas_pagamento.id"), nullable=True)
    conta_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("finance_contas.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
