from __future__ import annotations

import json
import sqlite3
from typing import Iterable


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def upsert_image(
    conn: sqlite3.Connection,
    path: str,
    mtime: int,
    size: int,
    hash_value: str | None,
    tags: Iterable[str] | None = None,
) -> int:
    tags_json = json.dumps(list(tags or []), ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO images(path, mtime, size, hash, tags_json)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
          mtime=excluded.mtime,
          size=excluded.size,
          hash=excluded.hash,
          tags_json=excluded.tags_json
        """,
        (path, mtime, size, hash_value, tags_json),
    )
    row = conn.execute("SELECT id FROM images WHERE path = ?", (path,)).fetchone()
    return int(row[0])


def replace_tags(conn: sqlite3.Connection, image_id: int, tags: Iterable[str]) -> None:
    conn.execute("DELETE FROM tags WHERE image_id = ?", (image_id,))
    rows = [(image_id, tag) for tag in tags]
    if rows:
        conn.executemany("INSERT INTO tags(image_id, tag) VALUES (?, ?)", rows)
