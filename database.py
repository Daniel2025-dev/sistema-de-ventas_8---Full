from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


PROJECT_DIR = Path(__file__).resolve().parent
SQLITE_PATH = PROJECT_DIR / "database.db"


def database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def is_postgres() -> bool:
    return database_url().startswith(("postgres://", "postgresql://"))


def backend_name() -> str:
    return "supabase" if is_postgres() else "sqlite"


def _postgres_query(query: str) -> str:
    """Translate the small SQLite SQL subset used by the legacy screens."""
    translated = query.replace("IFNULL(", "COALESCE(")
    translated = re.sub(r"\browid\b", "id", translated, flags=re.IGNORECASE)
    translated = translated.replace("INSERT OR IGNORE INTO", "INSERT INTO")
    translated = translated.replace("?", "%s")
    if "INSERT OR IGNORE INTO" in query.upper() and "ON CONFLICT" not in translated.upper():
        translated = f"{translated.rstrip().rstrip(';')} ON CONFLICT DO NOTHING"
    return translated


class CursorAdapter:
    def __init__(self, cursor: Any, postgres: bool) -> None:
        self._cursor = cursor
        self._postgres = postgres

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> "CursorAdapter":
        self._cursor.execute(_postgres_query(query) if self._postgres else query, params)
        return self

    def executemany(self, query: str, params: list[tuple[Any, ...]]) -> "CursorAdapter":
        self._cursor.executemany(_postgres_query(query) if self._postgres else query, params)
        return self

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> list[Any]:
        return self._cursor.fetchall()

    @property
    def description(self) -> Any:
        return self._cursor.description

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount


class ConnectionAdapter:
    def __init__(self, connection: Any, postgres: bool) -> None:
        self._connection = connection
        self._postgres = postgres

    def cursor(self) -> CursorAdapter:
        if self._postgres:
            from psycopg.rows import dict_row

            return CursorAdapter(self._connection.cursor(row_factory=dict_row), True)
        return CursorAdapter(self._connection.cursor(), False)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "ConnectionAdapter":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


def connect() -> ConnectionAdapter:
    if is_postgres():
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError(
                "DATABASE_URL usa PostgreSQL, pero falta instalar psycopg. "
                "Ejecute: pip install -r requirements.txt"
            ) from error
        return ConnectionAdapter(psycopg.connect(database_url()), True)

    connection = sqlite3.connect(SQLITE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return ConnectionAdapter(connection, False)


def rows_as_dicts(cursor: CursorAdapter, rows: list[Any]) -> list[dict[str, Any]]:
    if is_postgres():
        return [dict(row) for row in rows]
    return [dict(row) for row in rows]


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connect() as connection:
        cursor = connection.cursor().execute(query, params)
        return rows_as_dicts(cursor, cursor.fetchall())


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    rows = fetch_all(query, params)
    return rows[0] if rows else None


def fetch_scalar(query: str, params: tuple[Any, ...] = (), default: Any = None) -> Any:
    row = fetch_one(query, params)
    return next(iter(row.values())) if row else default


def execute(query: str, params: tuple[Any, ...] = ()) -> None:
    with connect() as connection:
        connection.cursor().execute(query, params)


@contextmanager
def transaction() -> Iterator[CursorAdapter]:
    connection = connect()
    cursor = connection.cursor()
    try:
        yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def validate_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Identificador SQL no permitido: {value}")
    return value


def next_document_number(document: str) -> int:
    if document not in {"factura", "cotizacion"}:
        raise ValueError("Tipo de documento no permitido")
    if is_postgres():
        sequence = "factura_numero_seq" if document == "factura" else "cotizacion_numero_seq"
        return int(fetch_scalar(f"SELECT nextval('{sequence}')", default=1))
    column = "factura" if document == "factura" else "cotizacion"
    table = "ventas" if document == "factura" else "cotizaciones"
    return int(fetch_scalar(f"SELECT COALESCE(MAX({column}), 0) + 1 FROM {table}", default=1))
