# app/routers/api_pedidos_exame.py
from __future__ import annotations

import os
import re
import logging
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

from app.services.pdf_service import extract_text_from_pdf_bytes

# ✅ IA: texto e imagem
from app.services.ai_service import (
    analyze_exam_or_rx_text,
    analyze_exam_or_rx_image_bytes,
)

logger = logging.getLogger("uvicorn.error")

router = APIRouter(tags=["API - IA (Pedidos/Receitas)"])

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _guess_doc_type(filename: str, text: str) -> Optional[str]:
    """
    Retorna:
      - "pedido_exame"
      - "receita"
      - None (indefinido)
    """
    fn = _norm(filename)
    t = _norm(text)

    pedido_kw = [
        "pedido de exame",
        "solicitacao de exame",
        "solicitação de exame",
        "exames solicitados",
        "requisição de exames",
        "requisicao de exames",
    ]
    receita_kw = [
        "receituario",
        "receituário",
        "receita",
        "prescricao",
        "prescrição",
        "rx",
    ]

    if any(k in fn for k in ["pedido", "exame", "solicitacao", "solicitação", "requisicao", "requisição"]):
        return "pedido_exame"
    if any(k in fn for k in ["receita", "receituario", "receituário", "prescricao", "prescrição", "rx"]):
        return "receita"

    if any(k in t for k in pedido_kw):
        return "pedido_exame"
    if any(k in t for k in receita_kw):
        return "receita"

    if ("posologia" in t or "tomar" in t or "mg" in t or "ml" in t) and ("crm" in t or "dr" in t or "dra" in t):
        return "receita"

    return None


async def _read_upload_bytes(upload: UploadFile) -> bytes:
    data = await upload.read()
    if not data or len(data) < 5:
        raise HTTPException(status_code=400, detail="Arquivo vazio ou inválido.")
    return data


def _is_pdf(data: bytes) -> bool:
    return bool(data[:4] == b"%PDF")


def _is_image_mime(mime: str) -> bool:
    m = (mime or "").lower().strip()
    return m in ("image/jpeg", "image/jpg", "image/png", "image/webp")


def _require_openai_key() -> None:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise HTTPException(
            status_code=501,
            detail="OPENAI_API_KEY não configurada no servidor. Configure no Render e faça redeploy.",
        )


# ------------------------------------------------------------
# Endpoint ÚNICO + aliases (para não quebrar o app)
# ------------------------------------------------------------
@router.post("/api/pedidos-exame/ler")
@router.post("/api/pedidos_exame/ler")
@router.post("/api/pedidos-exame/ler-arquivo")
@router.post("/api/pedidos-exame/upload")
@router.post("/api/pedidos-exame/analisar")
@router.post("/api/ia/ler")
@router.post("/api/ai/ler")
async def ler_documento_para_ia(
    # aceita vários nomes de campo (compatibilidade)
    file: Optional[UploadFile] = File(default=None),
    pdf: Optional[UploadFile] = File(default=None),
    arquivo: Optional[UploadFile] = File(default=None),
    documento: Optional[UploadFile] = File(default=None),

    # meta
    source: Optional[str] = Form(default=None),
    original_filename: Optional[str] = Form(default=None),

    # opcional: força tipo
    # "pedido_exame" | "receita"
    document_type: Optional[str] = Form(default=None),
) -> JSONResponse:
    upload = file or pdf or arquivo or documento
    if upload is None:
        raise HTTPException(status_code=422, detail="Arquivo obrigatório (file/pdf/arquivo/documento).")

    filename = (original_filename or upload.filename or "documento").strip() or "documento"
    mime = (upload.content_type or "").strip().lower()

    try:
        data = await _read_upload_bytes(upload)

        # 🔐 valida OPENAI key (antes de gastar processamento)
        _require_openai_key()

        # 1) Se for PDF → extrai texto
        if _is_pdf(data):
            extracted_text, pages = extract_text_from_pdf_bytes(data)

            if not extracted_text:
                # PDF escaneado (imagem) ou vazio
                return JSONResponse(
                    status_code=200,
                    content={
                        "ok": True,
                        "message": "PDF recebido, mas não foi possível extrair texto (provável PDF escaneado).",
                        "meta": {
                            "filename": filename,
                            "size_bytes": len(data),
                            "pages": pages,
                            "source": source,
                            "content_type": mime or "application/pdf",
                        },
                        "analysis": {
                            "tipo_documento": "indefinido",
                            "recusa": True,
                            "motivo_recusa": (
                                "O PDF parece escaneado (imagem) ou não possui texto. "
                                "Envie um PDF com texto selecionável OU envie uma imagem (JPG/PNG) legível."
                            ),
                        },
                    },
                )

            # determina tipo
            dt = (document_type or "").strip().lower()
            if dt not in ("pedido_exame", "receita", ""):
                raise HTTPException(status_code=422, detail="document_type inválido. Use 'pedido_exame' ou 'receita'.")

            doc_type = dt or _guess_doc_type(filename, extracted_text)
            if doc_type not in ("pedido_exame", "receita"):
                raise HTTPException(
                    status_code=422,
                    detail="Documento recusado: a IA só lê PEDIDOS DE EXAMES e RECEITAS.",
                )

            analysis = analyze_exam_or_rx_text(extracted_text, doc_type=doc_type)

            if isinstance(analysis, dict) and analysis.get("recusa") is True:
                raise HTTPException(status_code=422, detail=analysis.get("motivo_recusa") or "Documento recusado.")

            return JSONResponse(
                status_code=200,
                content={
                    "ok": True,
                    "message": "Análise concluída com sucesso.",
                    "meta": {
                        "filename": filename,
                        "size_bytes": len(data),
                        "pages": pages,
                        "source": source,
                        "document_type": doc_type,
                        "content_type": "application/pdf",
                    },
                    "analysis": analysis,
                },
            )

        # 2) Se for imagem → visão
        if _is_image_mime(mime):
            dt = (document_type or "").strip().lower()
            # para imagem a gente aceita também "exame" (teu ai_service mapeia)
            if dt not in ("pedido_exame", "receita", "exame", "laudo", "resultado_exame", ""):
                raise HTTPException(status_code=422, detail="document_type inválido para imagem.")

            doc_type = dt or "exame"  # default mais comum em foto
            analysis = analyze_exam_or_rx_image_bytes(data, mime_type=mime, doc_type=doc_type)

            if isinstance(analysis, dict) and analysis.get("recusa") is True:
                raise HTTPException(status_code=422, detail=analysis.get("motivo_recusa") or "Documento recusado.")

            return JSONResponse(
                status_code=200,
                content={
                    "ok": True,
                    "message": "Análise concluída com sucesso.",
                    "meta": {
                        "filename": filename,
                        "size_bytes": len(data),
                        "source": source,
                        "document_type": doc_type,
                        "content_type": mime,
                    },
                    "analysis": analysis,
                },
            )

        # 3) Se não for PDF nem imagem
        raise HTTPException(
            status_code=415,
            detail="Formato não suportado. Envie PDF ou imagem (JPG/PNG/WEBP).",
        )

    except HTTPException:
        raise
    except Exception as e:
        # loga stacktrace completo no Render
        logger.exception("Falha ao processar documento para IA: %s", e)
        # devolve mensagem amigável
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": "Falha interna ao analisar o documento. Verifique logs do servidor.",
            },
        )
