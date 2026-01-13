# app/routers/api_pedidos_exame.py
from __future__ import annotations

import os
import re
from typing import Optional, Any, Dict, Tuple

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

from app.services.pdf_service import extract_text_from_pdf_bytes
from app.services.ai_service import analyze_exam_or_rx_text

router = APIRouter(tags=["API - IA (Pedidos/Receitas)"])


async def _read_pdf_bytes(upload: UploadFile) -> bytes:
    data = await upload.read()
    if not data or len(data) < 5:
        raise HTTPException(status_code=400, detail="Arquivo vazio ou inválido.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Arquivo não parece ser um PDF válido.")
    return data


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
    Heurística leve + segura.
    """
    fn = _norm(filename)
    t = _norm(text)

    # Palavras-chave fortes
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

    # Arquivo
    if any(k in fn for k in ["pedido", "exame", "solicitacao", "solicitação", "requisicao", "requisição"]):
        return "pedido_exame"
    if any(k in fn for k in ["receita", "receituario", "receituário", "prescricao", "prescrição", "rx"]):
        return "receita"

    # Texto extraído
    if any(k in t for k in pedido_kw):
        return "pedido_exame"
    if any(k in t for k in receita_kw):
        return "receita"

    # Padrões comuns de receita (dose / posologia)
    if ("posologia" in t or "tomar" in t or "mg" in t or "ml" in t) and ("crm" in t or "dr" in t or "dra" in t):
        return "receita"

    return None


@router.post("/api/pedidos-exame/ler")
@router.post("/api/pedidos_exame/ler")  # alias
async def ler_pdf_para_ia(
    file: Optional[UploadFile] = File(default=None),
    pdf: Optional[UploadFile] = File(default=None),
    arquivo: Optional[UploadFile] = File(default=None),
    documento: Optional[UploadFile] = File(default=None),

    source: Optional[str] = Form(default=None),
    original_filename: Optional[str] = Form(default=None),

    # ✅ Novo (opcional): app pode mandar "pedido_exame" ou "receita"
    document_type: Optional[str] = Form(default=None),
) -> JSONResponse:
    upload = file or pdf or arquivo or documento
    if upload is None:
        raise HTTPException(status_code=422, detail="Arquivo obrigatório (file/pdf/arquivo/documento).")

    pdf_bytes = await _read_pdf_bytes(upload)

    filename = (original_filename or upload.filename or "documento.pdf").strip() or "documento.pdf"
    size_bytes = len(pdf_bytes)

    # Extrai texto
    extracted_text, pages = extract_text_from_pdf_bytes(pdf_bytes)

    if not extracted_text:
        return JSONResponse(
            content={
                "ok": True,
                "message": "PDF recebido, mas não foi possível extrair texto.",
                "meta": {"filename": filename, "size_bytes": size_bytes, "pages": pages, "source": source},
                "analysis": {
                    "tipo_documento": "indefinido",
                    "recusa": True,
                    "motivo_recusa": "O PDF parece escaneado (imagem) ou não possui texto. Envie um PDF exportado do sistema (texto selecionável).",
                },
            },
            status_code=200,
        )

    # Determina tipo de documento
    dt = (document_type or "").strip().lower()
    if dt not in ("pedido_exame", "receita", ""):
        raise HTTPException(status_code=422, detail="document_type inválido. Use 'pedido_exame' ou 'receita'.")

    doc_type = dt or _guess_doc_type(filename, extracted_text)
    if doc_type not in ("pedido_exame", "receita"):
        raise HTTPException(
            status_code=422,
            detail="Documento recusado: a IA só lê PEDIDOS DE EXAMES e RECEITAS. Envie apenas esses documentos.",
        )

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise HTTPException(status_code=501, detail="OPENAI_API_KEY não configurada no servidor. Configure no Render e faça redeploy.")

    try:
        analysis = analyze_exam_or_rx_text(extracted_text, doc_type=doc_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao analisar com IA: {e}")

    # Se a própria IA recusar (camada extra de segurança)
    if isinstance(analysis, dict) and analysis.get("recusa") is True:
        raise HTTPException(status_code=422, detail=analysis.get("motivo_recusa") or "Documento recusado.")

    return JSONResponse(
        content={
            "ok": True,
            "message": "Análise concluída com sucesso.",
            "meta": {"filename": filename, "size_bytes": size_bytes, "pages": pages, "source": source, "document_type": doc_type},
            "analysis": analysis,
        },
        status_code=200,
    )
