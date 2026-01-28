# app/schemas/auth.py
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    cpf: str = Field(..., min_length=3)
    senha: str = Field(..., min_length=1)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    paciente_id: int
    nome_completo: str
    cpf: str


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


# ✅ NOVO: troca de senha logado (via Bearer token)
class ChangePasswordIn(BaseModel):
    senha_atual: str
    nova_senha: str
    repetir_senha: str
