# app/routers/api_pedidos_exame.py
from __future__ import annotations

import os
import re
from typing import Optional, Dict, Any, Tuple

from fastapi import APIRouter, UploadFile, File, Form, Body, HTTPException
from fastapi.responses import JSONResponse

from app.services.pdf_service import extract_text_from_pdf_bytes
from app.services.ai_service import analyze_exam_or_rx_text, analyze_exam_or_rx_image_bytes


router = APIRouter(tags=["API - IA (Pedidos/Receitas)"])


# -----------------------------
# Helpers
# -----------------------------
def _norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _guess_doc_type(filename: str, text: str) -> Optional[str]:
    fn = _norm(filename)
    t = _norm(text)

    # pedido/exame
    if any(k in fn for k in ["pedido", "exame", "solicitacao", "solicitação", "requisicao", "requisição"]):
        return "pedido_exame"

    # receita
    if any(k in fn for k in ["receita", "receituario", "receituário", "prescricao", "prescrição", "rx"]):
        return "receita"

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
        "prescricao",
        "prescrição",
        "posologia",
        "tomar",
    ]

    if any(k in t for k in pedido_kw):
        return "pedido_exame"
    if any(k in t for k in receita_kw):
        return "receita"

    # heurística leve
    if ("mg" in t or "ml" in t) and ("crm" in t or "dr" in t or "dra" in t or "posologia" in t):
        return "receita"

    return None


async def _pick_upload(
    file: Optional[UploadFile],
    pdf: Optional[UploadFile],
    arquivo: Optional[UploadFile],
    documento: Optional[UploadFile],
) -> Optional[UploadFile]:
    return file or pdf or arquivo or documento


async def _read_bytes(upload: UploadFile) -> bytes:
    data = await upload.read()
    if not data or len(data) < 5:
        raise HTTPException(status_code=400, detail="Arquivo vazio ou inválido.")
    return data


def _ensure_openai_key():
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise HTTPException(
            status_code=501,
            detail="OPENAI_API_KEY não configurada no servidor (Render). Configure e faça redeploy.",
        )


def _resolve_doc_type(document_type: Optional[str], filename: str, extracted_text: str) -> str:
    # aceita vários valores do app
    dt = _norm(document_type or "")
    aliases = {
        "pedido_exame": "pedido_exame",
        "pedido-exame": "pedido_exame",
        "exame": "pedido_exame",
        "exames": "pedido_exame",
        "pedido": "pedido_exame",
        "receita": "receita",
        "rx": "receita",
        "prescricao": "receita",
        "prescrição": "receita",
    }
    if dt in aliases:
        return aliases[dt]

    guessed = _guess_doc_type(filename, extracted_text)
    if guessed in ("pedido_exame", "receita"):
        return guessed

    # fallback seguro: se não dá pra saber, recusa
    raise HTTPException(
        status_code=422,
        detail="Documento recusado: a IA só lê PEDIDOS DE EXAMES e RECEITAS. Envie apenas esses documentos.",
    )


# ============================================================
# ENDPOINT ÚNICO (processa: PDF texto / imagem / texto puro)
# ============================================================
async def _handle_request(
    *,
    upload: Optional[UploadFile],
    text: Optional[str],
    document_type: Optional[str],
    original_filename: Optional[str],
    source: Optional[str],
) -> JSONResponse:
    _ensure_openai_key()

    extracted_text = ""
    filename = (original_filename or (upload.filename if upload else "") or "documento").strip() or "documento"
    meta: Dict[str, Any] = {"filename": filename, "source": source}

    # 1) Se veio texto direto (JSON/Form)
    if text and text.strip():
        extracted_text = text.strip()
        meta["mode"] = "text"
        doc_type = _resolve_doc_type(document_type, filename, extracted_text)
        analysis = analyze_exam_or_rx_text(extracted_text, doc_type=doc_type)
        return JSONResponse(
            status_code=200,
            content={"ok": True, "message": "Análise concluída com sucesso.", "meta": {**meta, "document_type": doc_type}, "analysis": analysis},
        )

    # 2) Se veio arquivo
    if upload is None:
        # aqui é o ponto que estava causando 422: nada veio no body
        raise HTTPException(status_code=422, detail="Arquivo obrigatório (file/pdf/arquivo/documento) ou campo 'text'.")

    data = await _read_bytes(upload)
    meta["size_bytes"] = len(data)

    # 2a) PDF
    if (upload.content_type or "").lower() == "application/pdf" or filename.lower().endswith(".pdf"):
        if not data.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="Arquivo não parece ser um PDF válido.")

        extracted_text, pages = extract_text_from_pdf_bytes(data)
        meta["pages"] = pages
        meta["mode"] = "pdf"

        if not extracted_text.strip():
            # PDF escaneado: não tem texto -> recusa amigável
            return JSONResponse(
                status_code=200,
                content={
                    "ok": True,
                    "message": "PDF recebido, mas não foi possível extrair texto.",
                    "meta": meta,
                    "analysis": {
                        "tipo_documento": "indefinido",
                        "resumo": "",
                        "pontos_atencao": [],
                        "orientacoes": [],
                        "quando_procurar_urgencia": [],
                        "perguntas_para_medico": [],
                        "recusa": True,
                        "motivo_recusa": "O PDF parece escaneado (imagem) ou não possui texto. Envie um PDF com texto selecionável.",
                    },
                },
            )

        doc_type = _resolve_doc_type(document_type, filename, extracted_text)
        analysis = analyze_exam_or_rx_text(extracted_text, doc_type=doc_type)
        return JSONResponse(
            status_code=200,
            content={"ok": True, "message": "Análise concluída com sucesso.", "meta": {**meta, "document_type": doc_type}, "analysis": analysis},
        )

    # 2b) Imagem (jpg/png/webp)
    mime = (upload.content_type or "").lower()
    if mime in ("image/jpeg", "image/jpg", "image/png", "image/webp"):
        meta["mode"] = "image"
        doc_type = _resolve_doc_type(document_type, filename, extracted_text="")  # guess por filename ou doc_type
        analysis = analyze_exam_or_rx_image_bytes(data, mime_type=mime, doc_type=doc_type)
        return JSONResponse(
            status_code=200,
            content={"ok": True, "message": "Análise concluída com sucesso.", "meta": {**meta, "document_type": doc_type}, "analysis": analysis},
        )

    raise HTTPException(status_code=400, detail="Formato não suportado. Envie PDF ou imagem (JPG/PNG/WEBP) ou 'text'.")


# ============================================================
# ROTAS (todas as variantes que o app está chamando)
# ============================================================

# ✅ rota principal (a que você queria)
@router.post("/api/pedidos-exame/ler")
async def ler(
    file: Optional[UploadFile] = File(default=None),
    pdf: Optional[UploadFile] = File(default=None),
    arquivo: Optional[UploadFile] = File(default=None),
    documento: Optional[UploadFile] = File(default=None),
    text: Optional[str] = Form(default=None),
    source: Optional[str] = Form(default=None),
    original_filename: Optional[str] = Form(default=None),
    document_type: Optional[str] = Form(default=None),
    payload: Optional[dict] = Body(default=None),
):
    upload = await _pick_upload(file, pdf, arquivo, documento)
    text_from_json = (payload or {}).get("text") if isinstance(payload, dict) else None
    return await _handle_request(
        upload=upload,
        text=text or text_from_json,
        document_type=document_type or (payload or {}).get("document_type") if isinstance(payload, dict) else document_type,
        original_filename=original_filename,
        source=source,
    )


# ✅ aliases que o app está tentando (pra parar o 422/404)
@router.post("/api/pedidos-exame/ler-arquivo")
@router.post("/api/pedidos-exame/analisar")
@router.post("/api/pedidos-exame/upload")
@router.post("/api/ia/ler")
@router.post("/api/ai/ler")
async def ler_alias(
    file: Optional[UploadFile] = File(default=None),
    pdf: Optional[UploadFile] = File(default=None),
    arquivo: Optional[UploadFile] = File(default=None),
    documento: Optional[UploadFile] = File(default=None),
    text: Optional[str] = Form(default=None),
    source: Optional[str] = Form(default=None),
    original_filename: Optional[str] = Form(default=None),
    document_type: Optional[str] = Form(default=None),
    payload: Optional[dict] = Body(default=None),
):
    upload = await _pick_upload(file, pdf, arquivo, documento)
    text_from_json = (payload or {}).get("text") if isinstance(payload, dict) else None
    return await _handle_request(
        upload=upload,
        text=text or text_from_json,
        document_type=document_type or (payload or {}).get("document_type") if isinstance(payload, dict) else document_type,
        original_filename=original_filename,
        source=source,
    )
