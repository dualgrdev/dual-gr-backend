from __future__ import annotations

import io
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings, allowed_mimes, max_upload_bytes
from app.db.session import SessionLocal
from app.models import Empresa, Campanha, MaterialApoio
from app.services.storage import ensure_storage_dir


router = APIRouter(prefix="/api/public", tags=["Public (App)"])


# =========================
# DB
# =========================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================
# Helpers: upload / pdf / parsing
# =========================
def _only_digits(s: str) -> str:
    return re.sub(r"\D+", "", (s or ""))


def _safe_filename(original: str, ext: str) -> str:
    original = (original or "").strip()
    base = Path(original).stem if original else "arquivo"
    base = re.sub(r"[^a-zA-Z0-9._-]+", "_", base)[:80].strip("_") or "arquivo"
    return f"{base}_{uuid.uuid4().hex[:10]}{ext}"


async def _read_first_bytes(upload: UploadFile, n: int) -> bytes:
    # Lê sem perder o stream (volta ao início)
    pos = await upload.seek(0)
    head = await upload.read(n)
    await upload.seek(0)
    return head


async def _save_upload_to_disk(upload: UploadFile, dest_path: Path, max_bytes: int) -> int:
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    with dest_path.open("wb") as out:
        while True:
            chunk = await upload.read(1024 * 1024)  # 1MB
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Arquivo excede o limite de {int(max_bytes / (1024*1024))}MB.",
                )
            out.write(chunk)

    await upload.seek(0)
    return total


def _public_upload_url(rel_path: str) -> str:
    base = (settings.PUBLIC_BASE_URL or "").rstrip("/")
    # app/main.py monta /uploads apontando para o storage_dir
    return f"{base}/uploads/{rel_path.lstrip('/')}"


def _extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extrai texto quando o PDF é 'text-based'.
    Para PDF escaneado (imagem), vai vir vazio — aí a etapa OCR (se implementada) cobre.
    """
    try:
        # pypdf é o caminho mais estável hoje (substitui PyPDF2 em muitos ambientes)
        from pypdf import PdfReader  # type: ignore
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception:
            return ""

    try:
        reader = PdfReader(str(pdf_path))
        parts: List[str] = []
        for page in reader.pages:
            try:
                txt = page.extract_text() or ""
                if txt.strip():
                    parts.append(txt)
            except Exception:
                continue
        return "\n".join(parts).strip()
    except Exception:
        return ""


def _simple_exam_parser(text: str) -> Dict[str, Any]:
    """
    Fallback simples (sem IA): tenta identificar itens comuns.
    Com IA ligada, ela devolve estruturado com muito mais qualidade.
    """
    t = (text or "").strip()
    t_low = t.lower()

    # Heurística básica
    exames = []
    candidatos = [
        "hemograma", "glicose", "colesterol", "hdl", "ldl", "triglicerídeos", "triglicerideos",
        "tgo", "tgp", "ggt", "creatinina", "ureia", "tsh", "t4", "vitamina d", "ferritina",
        "urina", "eas", "parasitológico", "parasitologico", "pcr", "hb glicada", "hba1c",
    ]
    for c in candidatos:
        if c in t_low:
            exames.append(c.upper() if c.isalpha() else c)

    # Possível CPF
    cpf = ""
    m = re.search(r"\b(\d{3}\.?\d{3}\.?\d{3}-?\d{2})\b", t)
    if m:
        cpf = _only_digits(m.group(1))

    # Nome do paciente (bem heurístico)
    nome = ""
    m2 = re.search(r"(paciente|nome)\s*[:\-]\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇç\s]{5,})", t)
    if m2:
        nome = m2.group(2).strip()

    return {
        "paciente_nome": nome or None,
        "paciente_cpf": cpf or None,
        "exames_detectados": sorted(list(set(exames))) if exames else [],
        "observacoes": None,
    }


def _ai_extract_structured(text: str) -> Dict[str, Any]:
    """
    IA (OpenAI) para extrair estrutura a partir do texto.
    - Se AI_PROVIDER = "off" ou chave vazia -> fallback.
    """
    if (settings.AI_PROVIDER or "off").lower() != "openai":
        return {"provider": "off", "parsed": _simple_exam_parser(text)}

    api_key = (settings.OPENAI_API_KEY or "").strip()
    if not api_key:
        return {"provider": "openai_missing_key", "parsed": _simple_exam_parser(text)}

    # Tentativa com SDK (openai>=1.x). Se não estiver instalado, cai no fallback.
    try:
        from openai import OpenAI  # type: ignore
        client = OpenAI(api_key=api_key)

        prompt = f"""
Você é uma enfermeira virtual da Dual GR. Extraia dados estruturados a partir do texto de um pedido/resultado de exame.

Retorne SOMENTE JSON válido com as chaves:
- paciente_nome (string|null)
- paciente_cpf (string|null, somente dígitos)
- medico_nome (string|null)
- medico_crm (string|null)
- exames (lista de strings)
- observacoes (string|null)

Texto:
\"\"\"{text[:20000]}\"\"\"
""".strip()

        # SDK recente tem .responses.create; mas muitos ambientes ainda usam chat.completions
        parsed_obj: Optional[Dict[str, Any]] = None

        if hasattr(client, "responses"):
            resp = client.responses.create(
                model=settings.OPENAI_MODEL,
                input=prompt,
                temperature=float(getattr(settings, "AI_TEMPERATURE", 0.1)),
            )
            out = getattr(resp, "output_text", "") or ""
            parsed_obj = json_safe_load(out)
        else:
            chat = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Responda somente JSON válido, sem markdown."},
                    {"role": "user", "content": prompt},
                ],
                temperature=float(getattr(settings, "AI_TEMPERATURE", 0.1)),
            )
            out = (chat.choices[0].message.content or "").strip()
            parsed_obj = json_safe_load(out)

        if not parsed_obj:
            return {"provider": "openai_unparsed", "parsed": _simple_exam_parser(text)}

        # Normalizações mínimas
        cpf = _only_digits(str(parsed_obj.get("paciente_cpf") or ""))
        parsed_obj["paciente_cpf"] = cpf or None

        exames = parsed_obj.get("exames") or []
        if isinstance(exames, str):
            exames = [exames]
        if isinstance(exames, list):
            parsed_obj["exames"] = [str(x).strip() for x in exames if str(x).strip()]
        else:
            parsed_obj["exames"] = []

        return {"provider": "openai", "parsed": parsed_obj}

    except Exception:
        return {"provider": "openai_sdk_error", "parsed": _simple_exam_parser(text)}


def json_safe_load(s: str) -> Optional[Dict[str, Any]]:
    s = (s or "").strip()
    if not s:
        return None
    # tenta localizar bloco JSON dentro do texto
    try:
        return json.loads(s)
    except Exception:
        pass
    try:
        start = s.find("{")
        end = s.rfind("}")
        if start >= 0 and end > start:
            return json.loads(s[start : end + 1])
    except Exception:
        return None
    return None


# =========================
# Endpoints existentes
# =========================
@router.get("/empresas")
def listar_empresas(db: Session = Depends(get_db)):
    empresas = (
        db.query(Empresa)
        .filter(Empresa.is_active == True)
        .order_by(Empresa.nome.asc())
        .all()
    )
    return [{"id": e.id, "nome": e.nome} for e in empresas]


@router.get("/campanhas")
def listar_campanhas(db: Session = Depends(get_db)):
    campanhas = (
        db.query(Campanha)
        .filter(Campanha.is_active == True)
        .order_by(Campanha.ordem.asc(), Campanha.id.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "titulo": c.titulo,
            "mensagem": c.mensagem,
            "imagem_url": c.imagem_url,
            "ordem": c.ordem,
        }
        for c in campanhas
    ]


@router.get("/materiais")
def listar_materiais(db: Session = Depends(get_db)):
    materiais = (
        db.query(MaterialApoio)
        .filter(MaterialApoio.is_active == True)
        .order_by(MaterialApoio.id.desc())
        .all()
    )
    return [
        {
            "id": m.id,
            "titulo": m.titulo,
            "descricao": m.descricao,
            "tipo": m.tipo,
            "arquivo_url": m.arquivo_url,
        }
        for m in materiais
    ]


# =========================
# NOVO: Upload + IA leitura de exames (PDF)
# =========================
@router.post("/pedidos-exame/ler")
async def ler_pedido_exame_pdf(
    file: UploadFile = File(...),
    source: str = Form("app_dual_gr"),
    original_filename: str = Form(""),
):
    """
    Recebe PDF (pedido/resultado), salva no storage e retorna estrutura extraída pela IA.
    - Upload field: file
    - Retorno: JSON com upload + texto + parsed
    """

    # 1) valida MIME (quando presente)
    allowed = allowed_mimes()
    ct = (file.content_type or "").lower().strip()
    if allowed and ct and ct not in allowed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo de arquivo não permitido: {file.content_type}. Envie PDF/JPG/PNG.",
        )

    # 2) valida assinatura PDF (para este endpoint: exigimos PDF)
    head = await _read_first_bytes(file, 5)
    if not head.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo não parece ser um PDF válido (assinatura %PDF não encontrada).",
        )

    # 3) define destino no storage
    root = Path(ensure_storage_dir())  # respeita seu serviço/storage
    now = datetime.utcnow()
    subdir = Path("exames") / f"{now.year:04d}" / f"{now.month:02d}"
    ext = ".pdf"
    safe_name = _safe_filename(original_filename or file.filename or "exame.pdf", ext)
    rel_path = str((subdir / safe_name).as_posix())
    dest_path = root / rel_path

    # 4) salva respeitando limite de tamanho
    size = await _save_upload_to_disk(file, dest_path, max_upload_bytes())

    # 5) extrai texto do PDF
    text = _extract_text_from_pdf(dest_path)

    # 6) IA (ou fallback)
    ai = _ai_extract_structured(text)

    return {
        "ok": True,
        "source": source,
        "upload": {
            "filename": safe_name,
            "original_filename": original_filename or file.filename,
            "size_bytes": size,
            "relative_path": rel_path,
            "url": _public_upload_url(rel_path),
            "content_type": file.content_type,
        },
        "extracted": {
            "text_chars": len(text or ""),
            "text_preview": (text[:800] if text else ""),
        },
        "ai": ai,
    }
