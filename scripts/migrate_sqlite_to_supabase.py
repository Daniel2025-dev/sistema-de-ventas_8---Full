from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

import psycopg
from psycopg import sql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
TABLES = [
    "empresa", "moneda", "categorias", "sucursal", "impuestos", "clientes",
    "proveedores", "inventario", "caja", "ventas", "cotizaciones", "pedidos", "gastos",
]


def sqlite_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]


def postgres_columns(connection: psycopg.Connection, table: str) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",
            (table,),
        )
        return {row[0] for row in cursor.fetchall()}


def migrate(sqlite_path: Path, postgres_url: str, clear: bool) -> None:
    source = sqlite3.connect(sqlite_path)
    source.row_factory = sqlite3.Row
    target = psycopg.connect(postgres_url)
    try:
        with target.transaction():
            for table in TABLES:
                source_names = sqlite_columns(source, table)
                if not source_names:
                    continue
                target_names = postgres_columns(target, table)
                columns = [name.lower() for name in source_names if name.lower() in target_names]
                rows = source.execute(f'SELECT * FROM "{table}"').fetchall()
                if clear:
                    target.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier(table)))
                if not rows:
                    print(f"{table}: 0 registros")
                    continue
                statement = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(
                    sql.Identifier(table),
                    sql.SQL(", ").join(map(sql.Identifier, columns)),
                    sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                )
                values = [tuple(row[name] for name in source_names if name.lower() in target_names) for row in rows]
                target.executemany(statement, values)
                print(f"{table}: {len(values)} registros procesados")

            identity_tables = [table for table in TABLES if "id" in postgres_columns(target, table)]
            for table in identity_tables:
                target.execute(
                    sql.SQL(
                        "SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                        "GREATEST(COALESCE((SELECT MAX(id) FROM {}), 0), 1), true)"
                    ).format(sql.Identifier(table)),
                    (f"public.{table}",),
                )
            target.execute(
                "SELECT setval('factura_numero_seq', GREATEST(COALESCE((SELECT MAX(factura) FROM ventas), 0), 1), true)"
            )
            target.execute(
                "SELECT setval('cotizacion_numero_seq', GREATEST(COALESCE((SELECT MAX(cotizacion) FROM cotizaciones), 0), 1), true)"
            )
    finally:
        source.close()
        target.close()

    print("Migración terminada. Vincule los usuarios con Supabase Auth.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migra SQLite a Supabase PostgreSQL")
    parser.add_argument("--sqlite", type=Path, default=ROOT / "database.db")
    parser.add_argument("--clear", action="store_true")
    args = parser.parse_args()
    postgres_url = os.getenv("DATABASE_URL", "")
    if not postgres_url.startswith(("postgres://", "postgresql://")):
        sys.exit("Configure DATABASE_URL con la conexión PostgreSQL de Supabase")
    migrate(args.sqlite, postgres_url, args.clear)


if __name__ == "__main__":
    main()
