from pydantic import BaseModel, Field


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

    # ✅ extras para o app
    paciente_id: int
    nome_completo: str
    cpf: str


class LoginIn(BaseModel):
    cpf: str = Field(min_length=11, max_length=14)
    senha: str = Field(min_length=1)


class ForgotQuestionOut(BaseModel):
    pergunta: str


class ForgotVerifyIn(BaseModel):
    cpf: str
    resposta: str


class ResetPasswordIn(BaseModel):
    cpf: str
    resposta: str
    nova_senha: str
    repetir_senha: str
