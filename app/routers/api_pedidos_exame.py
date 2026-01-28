# app/routers/api_pedidos_exame.py
from __future__ import annotations

import os
import re
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

from app.services.pdf_service import extract_text_from_pdf_bytes
from app.services.ai_service import analyze_exam_or_rx_text, analyze_exam_or_rx_image_bytes

router = APIRouter(tags=["API - IA (Exames/Receitas)"])


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


async def _read_upload_bytes(upload: UploadFile) -> bytes:
    data = await upload.read()
    if not data or len(data) < 5:
        raise HTTPException(status_code=400, detail="Arquivo vazio ou inválido.")
    return data


def _is_pdf_bytes(data: bytes) -> bool:
    return bool(data) and data.startswith(b"%PDF")


def _guess_doc_type(filename: str, text: str) -> Optional[str]:
    """
    Retorna:
      - "exame"
      - "receita"
      - None
    """
    fn = _norm(filename)
    t = _norm(text)

    exame_kw = [
        "resultado de exame",
        "resultados de exames",
        "exames laboratoriais",
        "laboratório",
        "laboratorio",
        "hemograma",
        "glicose",
        "colesterol",
        "tgo",
        "tgp",
        "ggt",
        "ureia",
        "creatinina",
        "hdl",
        "ldl",
        "triglicer",
        "laudo",
        "resultado",
        "referência",
        "referencia",
        "valores de referência",
        "intervalo de referência",
    ]
    receita_kw = [
        "receituario",
        "receituário",
        "receita",
        "prescricao",
        "prescrição",
        "rx",
        "posologia",
    ]

    # filename
    if any(k in fn for k in ["exame", "laudo", "resultado", "laboratorio", "laboratório", "hemograma"]):
        return "exame"
    if any(k in fn for k in ["receita", "receituario", "receituário", "prescricao", "prescrição", "rx"]):
        return "receita"

    # extracted text
    if any(k in t for k in exame_kw):
        return "exame"
    if any(k in t for k in receita_kw):
        return "receita"

    # heurística de receita (dose/posologia + CRM)
    if ("posologia" in t or "tomar" in t or "mg" in t or "ml" in t) and ("crm" in t or "dr" in t or "dra" in t):
        return "receita"

    return None


@router.post("/api/pedidos-exame/ler")
@router.post("/api/pedidos_exame/ler")  # alias
async def ler_documento_para_ia(
    file: Optional[UploadFile] = File(default=None),
    pdf: Optional[UploadFile] = File(default=None),
    arquivo: Optional[UploadFile] = File(default=None),
    documento: Optional[UploadFile] = File(default=None),

    source: Optional[str] = Form(default=None),
    original_filename: Optional[str] = Form(default=None),

    # app pode mandar: "exame" ou "receita" (opcional)
    document_type: Optional[str] = Form(default=None),
) -> JSONResponse:
    upload = file or pdf or arquivo or documento
    if upload is None:
        raise HTTPException(status_code=422, detail="Arquivo obrigatório (file/pdf/arquivo/documento).")

    raw_bytes = await _read_upload_bytes(upload)

    filename = (original_filename or upload.filename or "documento").strip() or "documento"
    size_bytes = len(raw_bytes)

    # document_type explícito (se vier)
    dt = (document_type or "").strip().lower()
    if dt and dt not in ("exame", "receita"):
        raise HTTPException(status_code=422, detail="document_type inválido. Use 'exame' ou 'receita'.")

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise HTTPException(
            status_code=501,
            detail="OPENAI_API_KEY não configurada no servidor. Configure no Render e faça redeploy.",
        )

    # =========================
    # 1) PDF (texto extraível)
    # =========================
    if _is_pdf_bytes(raw_bytes):
        extracted_text, pages = extract_text_from_pdf_bytes(raw_bytes)

        if not extracted_text:
            return JSONResponse(
                content={
                    "ok": True,
                    "message": "PDF recebido, mas não foi possível extrair texto.",
                    "meta": {
                        "filename": filename,
                        "size_bytes": size_bytes,
                        "pages": pages,
                        "source": source,
                    },
                    "analysis": {
                        "tipo_documento": "indefinido",
                        "recusa": True,
                        "motivo_recusa": (
                            "O PDF parece escaneado (imagem) ou não possui texto. "
                            "Envie um PDF exportado do sistema (texto selecionável) ou envie a imagem legível do exame/receita."
                        ),
                    },
                },
                status_code=200,
            )

        doc_type = dt or _guess_doc_type(filename, extracted_text)
        if doc_type not in ("exame", "receita"):
            raise HTTPException(
                status_code=422,
                detail="Documento recusado: a IA só lê EXAMES e RECEITAS. Envie apenas esses documentos.",
            )

        try:
            analysis = analyze_exam_or_rx_text(extracted_text, doc_type=doc_type)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Falha ao analisar com IA: {e}")

        if isinstance(analysis, dict) and analysis.get("recusa") is True:
            raise HTTPException(status_code=422, detail=analysis.get("motivo_recusa") or "Documento recusado.")

        return JSONResponse(
            content={
                "ok": True,
                "message": "Análise concluída com sucesso.",
                "meta": {
                    "filename": filename,
                    "size_bytes": size_bytes,
                    "pages": pages,
                    "source": source,
                    "document_type": doc_type,
                },
                "analysis": analysis,
            },
            status_code=200,
        )

    # =========================
    # 2) IMAGEM (jpg/png/webp)
    # =========================
    # tenta inferir mime pelo header do UploadFile; fallback por extensão
    mime = (upload.content_type or "").strip().lower()
    if not mime or mime == "application/octet-stream":
        fn = _norm(filename)
        if fn.endswith(".png"):
            mime = "image/png"
        elif fn.endswith(".webp"):
            mime = "image/webp"
        else:
            mime = "image/jpeg"

    if mime not in ("image/jpeg", "image/jpg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=415,
            detail="Formato não suportado. Envie PDF (texto) ou imagem JPG/PNG/WEBP.",
        )

    # se dt não veio, deixamos a IA decidir recusando se não for exame/receita
    doc_type = dt or "exame"

    try:
        analysis = analyze_exam_or_rx_image_bytes(raw_bytes, mime_type=mime, doc_type=doc_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao analisar imagem com IA: {e}")

    if isinstance(analysis, dict) and analysis.get("recusa") is True:
        raise HTTPException(status_code=422, detail=analysis.get("motivo_recusa") or "Documento recusado.")

    return JSONResponse(
        content={
            "ok": True,
            "message": "Análise concluída com sucesso.",
            "meta": {
                "filename": filename,
                "size_bytes": size_bytes,
                "pages": None,
                "source": source,
                "document_type": doc_type,
                "content_type": mime,
            },
            "analysis": analysis,
        },
        status_code=200,
    )
