import os
import uuid
from pathlib import Path
from typing import Optional

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


def save_upload_local(file: UploadFile, subdir: str, allowed_exts: set[str]) -> str:
    """
    Salva arquivo no storage local e retorna URL pública.
    """
    base = ensure_storage_dir()
    folder = base / subdir
    folder.mkdir(parents=True, exist_ok=True)

    ext = safe_ext(file.filename)
    if ext not in allowed_exts:
        raise ValueError(f"Extensão inválida: {ext}")

    new_name = f"{uuid.uuid4().hex}{ext}"
    dst = folder / new_name

    # streaming simples
    with dst.open("wb") as f:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    # URL pública (servida pelo backend via /uploads)
    return f"{settings.PUBLIC_BASE_URL}/uploads/{subdir}/{new_name}"
