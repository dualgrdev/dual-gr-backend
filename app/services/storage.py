import os
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings


def ensure_storage_dir() -> Path:
    base = Path(settings.LOCAL_STORAGE_PATH).resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base


def safe_ext(filename: str) -> str:
    name = (filename or "").strip()
    ext = os.path.splitext(name)[1].lower()
    if not ext or len(ext) > 10:
        return ""
    return ext


def _join_public_url(*parts: str) -> str:
    base = (settings.PUBLIC_BASE_URL or "").rstrip("/")
    path = "/".join([p.strip("/").lstrip("/") for p in parts if p is not None])
    return f"{base}/{path}"


def save_upload_local(file: UploadFile, subdir: str, allowed_exts: set[str]) -> str:
    """
    Salva arquivo no storage local e retorna URL pública (servida via /uploads).
    Observação: em Render, o filesystem pode não ser persistente sem disco persistente.
    """
    base = ensure_storage_dir()
    folder = base / subdir
    folder.mkdir(parents=True, exist_ok=True)

    ext = safe_ext(file.filename)
    if ext not in allowed_exts:
        raise ValueError(f"Extensão inválida: {ext}")

    new_name = f"{uuid.uuid4().hex}{ext}"
    dst = folder / new_name

    # streaming simples (sincrono)
    with dst.open("wb") as f:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    return _join_public_url("uploads", subdir, new_name)
