# app/services/pdf_service.py
from __future__ import annotations

from typing import Tuple
from pypdf import PdfReader
import io


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> Tuple[str, int]:
    """
    Retorna (texto, num_paginas). Texto pode vir vazio se PDF for escaneado/imagem.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = len(reader.pages)
    parts = []
    for p in reader.pages:
        try:
            t = p.extract_text() or ""
        except Exception:
            t = ""
        t = t.strip()
        if t:
            parts.append(t)
    return ("\n\n".join(parts).strip(), pages)
