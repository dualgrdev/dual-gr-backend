from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class PacienteCreate(BaseModel):
    nome_completo: str = Field(min_length=3, max_length=200)

    # ✅ NOVO
    email: EmailStr

    cpf: str
    celular: str

    empresa_id: Optional[int] = None
    empresa: Optional[str] = None

    endereco: str = Field(min_length=5, max_length=250)
    cep: str

    senha: str
    repetir_senha: str

    pergunta_seg: str = Field(min_length=3, max_length=200)
    resposta_seg: str = Field(min_length=1, max_length=200)


class PacienteOut(BaseModel):
    id: int
    nome_completo: str
    email: str
    cpf: str
    celular: str
    empresa: str
    endereco: str
    cep: str

    class Config:
        from_attributes = True
