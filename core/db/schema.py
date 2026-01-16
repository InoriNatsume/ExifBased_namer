from __future__ import annotations

import sqlite3
from pathlib import Path


def load_schema_sql() -> str:
    root = Path(__file__).resolve().parents[2]
    schema_path = root / "db" / "schema.sql"
    return schema_path.read_text(encoding="utf-8")


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.Error:
        return set()
    return {row[1] for row in rows}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row)


def _get_schema_version(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "meta"):
        return 0
    row = conn.execute("SELECT schema_version FROM meta").fetchone()
    if not row:
        return 0
    return int(row[0])


def ensure_schema(conn: sqlite3.Connection) -> None:
    schema_sql = load_schema_sql()

    # 마이그레이션: 인덱스 생성 전에 누락된 컬럼 추가
    if _table_exists(conn, "images"):
        images_cols = _table_columns(conn, "images")
        if "tags_pos_json" not in images_cols:
            conn.execute("ALTER TABLE images ADD COLUMN tags_pos_json TEXT")
        if "tags_neg_json" not in images_cols:
            conn.execute("ALTER TABLE images ADD COLUMN tags_neg_json TEXT")
        if "tags_char_json" not in images_cols:
            conn.execute("ALTER TABLE images ADD COLUMN tags_char_json TEXT")

    if _table_exists(conn, "tags"):
        tags_cols = _table_columns(conn, "tags")
        if "source_type" not in tags_cols:
            conn.execute("ALTER TABLE tags ADD COLUMN source_type TEXT")
        if "source_idx" not in tags_cols:
            conn.execute("ALTER TABLE tags ADD COLUMN source_idx INTEGER")
        conn.execute(
            "UPDATE tags SET source_type = 'pos' WHERE source_type IS NULL"
        )

    # 스키마 적용 (테이블/인덱스 생성)
    conn.executescript(schema_sql)

    if not _table_exists(conn, "image_payloads"):
        conn.execute(
            """
            CREATE TABLE image_payloads (
              image_id INTEGER NOT NULL,
              payload_index INTEGER NOT NULL,
              payload_json TEXT NOT NULL,
              FOREIGN KEY(image_id) REFERENCES images(id) ON DELETE CASCADE
            )
            """
        )

    if not _table_exists(conn, "templates"):
        conn.execute(
            """
            CREATE TABLE templates (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL UNIQUE,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )

    if not _table_exists(conn, "presets"):
        conn.execute(
            """
            CREATE TABLE presets (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              source_kind TEXT NOT NULL,
              variable_name TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )

    conn.execute("CREATE INDEX IF NOT EXISTS idx_tags_tag_source ON tags(tag, source_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tags_image_id ON tags(image_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_payloads_image_id ON image_payloads(image_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_templates_name ON templates(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_presets_name ON presets(name)")

    version = _get_schema_version(conn)
    if version < 2:
        conn.execute("UPDATE meta SET schema_version = 2")
    conn.commit()
