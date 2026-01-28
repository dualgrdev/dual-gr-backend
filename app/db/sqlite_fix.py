# app/db/sqlite_fix.py
from sqlalchemy import text
from sqlalchemy.engine import Engine


def _is_sqlite(engine: Engine) -> bool:
    try:
        return engine.dialect.name == "sqlite"
    except Exception:
        return False


def _sqlite_has_column(engine: Engine, table: str, column: str) -> bool:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    # PRAGMA table_info: (cid, name, type, notnull, dflt_value, pk)
    return any((r[1] == column) for r in rows)


def ensure_sqlite_columns(engine: Engine) -> None:
    """
    Corrige bancos SQLite antigos no Render:
    - adiciona colunas que passaram a existir no Model mas não existem no arquivo .db antigo.
    """
    if not _is_sqlite(engine):
        return

    # ===== pacientes.email =====
    if not _sqlite_has_column(engine, "pacientes", "email"):
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE pacientes ADD COLUMN email VARCHAR(255)"))
