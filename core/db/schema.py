from __future__ import annotations

import sqlite3
from pathlib import Path


def load_schema_sql() -> str:
    root = Path(__file__).resolve().parents[2]
    schema_path = root / "db" / "schema.sql"
    return schema_path.read_text(encoding="utf-8")


def ensure_schema(conn: sqlite3.Connection) -> None:
    schema_sql = load_schema_sql()
    conn.executescript(schema_sql)
