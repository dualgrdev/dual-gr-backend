from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AnamneseRegistro(Base):
    __tablename__ = "anamnese_registros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    paciente_id: Mapped[int] = mapped_column(Integer, ForeignKey("pacientes.id"), index=True, nullable=False)
    paciente = relationship("Paciente")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Identificação (nome é redundante para histórico — mas ajuda no painel)
    nome_completo: Mapped[str] = mapped_column(String(200), nullable=False)
    data_nascimento: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    sexo_biologico: Mapped[str | None] = mapped_column(String(30), nullable=True)
    altura_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    peso_kg: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Queixa
    queixa_principal: Mapped[str] = mapped_column(String(300), nullable=False)

    # Sintomas (listas em JSON para rapidez)
    sintomas: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    sintoma_outro: Mapped[str | None] = mapped_column(String(200), nullable=True)
    intensidade_0a10: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frequencia: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ha_quanto_tempo: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # Doenças
    doencas: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    doencas_outros: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Medicamentos
    usa_medicamento: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    medicamento_nome: Mapped[str | None] = mapped_column(String(120), nullable=True)
    medicamento_dosagem: Mapped[str | None] = mapped_column(String(120), nullable=True)
    medicamento_frequencia: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Suplementos / alimentação / hábitos
    suplementos: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    refeicoes_dia: Mapped[str | None] = mapped_column(String(10), nullable=True)
    consumo_frequente: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    agua_dia: Mapped[str | None] = mapped_column(String(10), nullable=True)

    atividade_fisica: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sono_horas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sono_qualidade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tabagismo: Mapped[str | None] = mapped_column(String(10), nullable=True)
    alcool: Mapped[str | None] = mapped_column(String(10), nullable=True)
