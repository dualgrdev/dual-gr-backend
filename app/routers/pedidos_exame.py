# app/routers/pedidos_exame.py
from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any

# Se você já tem auth/jwt no projeto, reaproveite o mesmo dependency
# Ajuste o import abaixo para o seu projeto.
try:
    from app.dependencies import get_current_user  # exemplo
except Exception:
    get_current_user = None  # fallback se ainda não existir

router = APIRouter(tags=["Pedidos de Exame"], prefix="/api")

def _ensure_pdf(upload: UploadFile) -> None:
    # validação leve por content-type + assinatura
    if upload.content_type not in (None, "", "application/pdf"):
        # muitos clientes mandam application/octet-stream; não vamos bloquear por isso
        pass

async def _read_pdf_bytes(upload: UploadFile) -> bytes:
    data = await upload.read()
    if not data or len(data) < 5:
        raise HTTPException(status_code=400, detail="Arquivo vazio ou inválido.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Arquivo não parece ser um PDF válido.")
    return data

@router.post("/pedidos-exame/ler")
@router.post("/pedidos_exame/ler")  # alias
async def ler_pedido_exame(
    # Campo principal (app atual)
    file: Optional[UploadFile] = File(default=None),

    # Aliases para compatibilidade
    pdf: Optional[UploadFile] = File(default=None),
    arquivo: Optional[UploadFile] = File(default=None),
    documento: Optional[UploadFile] = File(default=None),

    source: Optional[str] = Form(default=None),
    original_filename: Optional[str] = Form(default=None),

    # ✅ Auth opcional (mantém compatibilidade)
    user: Optional[Dict[str, Any]] = Depends(get_current_user) if get_current_user else None,
):
    upload = file or pdf or arquivo or documento
    if upload is None:
        raise HTTPException(status_code=422, detail="Arquivo obrigatório (campo: file/pdf/arquivo/documento).")

    _ensure_pdf(upload)
    pdf_bytes = await _read_pdf_bytes(upload)

    # ------------------------------------------------------------------
    # Aqui entra sua lógica real de IA: extrair texto do PDF + chamar LLM.
    # Neste patch, devolvemos um JSON padrão para destravar o app.
    # ------------------------------------------------------------------

    filename = original_filename or upload.filename or "documento.pdf"
    size_bytes = len(pdf_bytes)

    result = {
        "ok": True,
        "message": "PDF recebido com sucesso.",
        "meta": {
            "filename": filename,
            "size_bytes": size_bytes,
            "source": source,
        },
        # Troque este campo pelo seu output real (resumo, achados, recomendações)
        "analysis": {
            "status": "stub",
            "note": "Endpoint criado. Conecte aqui a pipeline de IA (extração + análise).",
        },
    }

    return JSONResponse(content=result, status_code=200)
