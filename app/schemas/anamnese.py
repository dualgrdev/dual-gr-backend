from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class AnamneseCreate(BaseModel):
    data_nascimento: Optional[str] = None
    sexo_biologico: Optional[str] = None
    altura_cm: Optional[int] = None
    peso_kg: Optional[float] = None

    queixa_principal: str = Field(min_length=1, max_length=300)

    sintomas: List[str] = []
    sintoma_outro: Optional[str] = None
    intensidade_0a10: Optional[int] = None
    frequencia: Optional[str] = None
    ha_quanto_tempo: Optional[str] = None

    doencas: List[str] = []
    doencas_outros: Optional[str] = None

    usa_medicamento: bool = False
    medicamento_nome: Optional[str] = None
    medicamento_dosagem: Optional[str] = None
    medicamento_frequencia: Optional[str] = None

    suplementos: List[str] = []

    refeicoes_dia: Optional[str] = None
    consumo_frequente: List[str] = []
    agua_dia: Optional[str] = None

    atividade_fisica: Optional[str] = None
    sono_horas: Optional[int] = None
    sono_qualidade: Optional[str] = None
    tabagismo: Optional[str] = None
    alcool: Optional[str] = None


class AnamneseOut(BaseModel):
    id: int
    created_at: datetime

    nome_completo: str
    data_nascimento: Optional[str] = None
    sexo_biologico: Optional[str] = None
    altura_cm: Optional[int] = None
    peso_kg: Optional[float] = None

    queixa_principal: str

    sintomas: List[str] = []
    sintoma_outro: Optional[str] = None
    intensidade_0a10: Optional[int] = None
    frequencia: Optional[str] = None
    ha_quanto_tempo: Optional[str] = None

    doencas: List[str] = []
    doencas_outros: Optional[str] = None

    usa_medicamento: bool = False
    medicamento_nome: Optional[str] = None
    medicamento_dosagem: Optional[str] = None
    medicamento_frequencia: Optional[str] = None

    suplementos: List[str] = []

    refeicoes_dia: Optional[str] = None
    consumo_frequente: List[str] = []
    agua_dia: Optional[str] = None

    atividade_fisica: Optional[str] = None
    sono_horas: Optional[int] = None
    sono_qualidade: Optional[str] = None
    tabagismo: Optional[str] = None
    alcool: Optional[str] = None

    class Config:
        from_attributes = True
