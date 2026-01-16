from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Iterable


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def upsert_image(
    conn: sqlite3.Connection,
    path: str,
    mtime: int,
    size: int,
    hash_value: str | None,
    tags_pos: Iterable[str] | None = None,
    tags_neg: Iterable[str] | None = None,
    tags_char: Iterable[str] | None = None,
) -> int:
    tags_pos_json = json.dumps(list(tags_pos or []), ensure_ascii=False)
    tags_neg_json = json.dumps(list(tags_neg or []), ensure_ascii=False)
    tags_char_json = json.dumps(list(tags_char or []), ensure_ascii=False)
    combined = list(tags_pos or []) + list(tags_char or [])
    tags_json = json.dumps(combined, ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO images(path, mtime, size, hash, tags_json, tags_pos_json, tags_neg_json, tags_char_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
          mtime=excluded.mtime,
          size=excluded.size,
          hash=excluded.hash,
          tags_json=excluded.tags_json,
          tags_pos_json=excluded.tags_pos_json,
          tags_neg_json=excluded.tags_neg_json,
          tags_char_json=excluded.tags_char_json
        """,
        (path, mtime, size, hash_value, tags_json, tags_pos_json, tags_neg_json, tags_char_json),
    )
    row = conn.execute("SELECT id FROM images WHERE path = ?", (path,)).fetchone()
    return int(row[0])


def replace_tags(
    conn: sqlite3.Connection,
    image_id: int,
    tags: Iterable[tuple[str, str | None, int | None]],
) -> None:
    conn.execute("DELETE FROM tags WHERE image_id = ?", (image_id,))
    rows = [(image_id, tag, source_type, source_idx) for tag, source_type, source_idx in tags]
    if rows:
        conn.executemany(
            "INSERT INTO tags(image_id, tag, source_type, source_idx) VALUES (?, ?, ?, ?)",
            rows,
        )


def replace_payloads(conn: sqlite3.Connection, image_id: int, payloads: Iterable[dict]) -> None:
    conn.execute("DELETE FROM image_payloads WHERE image_id = ?", (image_id,))
    rows = [
        (image_id, idx, json.dumps(payload, ensure_ascii=False))
        for idx, payload in enumerate(payloads)
    ]
    if rows:
        conn.executemany(
            "INSERT INTO image_payloads(image_id, payload_index, payload_json) VALUES (?, ?, ?)",
            rows,
        )


def upsert_template(conn: sqlite3.Connection, name: str, payload: dict) -> int:
    now = _now_iso()
    payload_json = json.dumps(payload, ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO templates(name, payload_json, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
          payload_json=excluded.payload_json,
          updated_at=excluded.updated_at
        """,
        (name, payload_json, now, now),
    )
    row = conn.execute("SELECT id FROM templates WHERE name = ?", (name,)).fetchone()
    return int(row[0])


def delete_template(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute("DELETE FROM templates WHERE name = ?", (name,))
    return cur.rowcount > 0


def save_preset(
    conn: sqlite3.Connection,
    *,
    name: str,
    source_kind: str,
    variable_name: str,
    payload: dict,
    preset_id: int | None = None,
) -> int:
    now = _now_iso()
    payload_json = json.dumps(payload, ensure_ascii=False)
    if preset_id is None:
        conn.execute(
            """
            INSERT INTO presets(name, source_kind, variable_name, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, source_kind, variable_name, payload_json, now, now),
        )
        row = conn.execute("SELECT last_insert_rowid()").fetchone()
        return int(row[0])

    conn.execute(
        """
        UPDATE presets
        SET name = ?, source_kind = ?, variable_name = ?, payload_json = ?, updated_at = ?
        WHERE id = ?
        """,
        (name, source_kind, variable_name, payload_json, now, preset_id),
    )
    return preset_id


def delete_preset(conn: sqlite3.Connection, preset_id: int) -> bool:
    cur = conn.execute("DELETE FROM presets WHERE id = ?", (preset_id,))
    return cur.rowcount > 0
