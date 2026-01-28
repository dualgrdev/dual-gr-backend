# app/db/sqlite_bootstrap.py
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _is_sqlite(engine: Engine) -> bool:
    try:
        return engine.dialect.name == "sqlite"
    except Exception:
        return False


def ensure_sqlite_schema(engine: Engine) -> None:
    """
    Bootstrap idempotente para ambientes SQLite já existentes.
    - Evita crash por schema antigo (ex.: coluna pacientes.email ausente).
    - Só roda se o banco for SQLite.
    """
    if not _is_sqlite(engine):
        return

    with engine.begin() as conn:
        # -------------------------
        # pacientes: garantir email
        # -------------------------
        try:
            cols = conn.execute(text("PRAGMA table_info(pacientes)")).mappings().all()
            col_names = {c["name"] for c in cols}
        except Exception:
            # se a tabela ainda não existe, create_all cuidará disso
            return

        if "email" not in col_names:
            # SQLite permite ADD COLUMN (sem NOT NULL se já houver linhas)
            conn.execute(text("ALTER TABLE pacientes ADD COLUMN email VARCHAR(200)"))
