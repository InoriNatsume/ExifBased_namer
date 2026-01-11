from __future__ import annotations

import sqlite3
import json
from typing import Iterable


def count_images(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM images").fetchone()
    return int(row[0])


def count_tags(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM tags").fetchone()
    return int(row[0])


def count_matches(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM matches").fetchone()
    return int(row[0])


def get_image_meta(conn: sqlite3.Connection, path: str) -> tuple[int, int] | None:
    row = conn.execute(
        "SELECT mtime, size FROM images WHERE path = ?",
        (path,),
    ).fetchone()
    if not row:
        return None
    return int(row[0]), int(row[1])


def get_tags_for_path(conn: sqlite3.Connection, path: str) -> list[str] | None:
    row = conn.execute(
        "SELECT id, tags_json FROM images WHERE path = ?",
        (path,),
    ).fetchone()
    if not row:
        return None
    image_id = int(row[0])
    tags_json = row[1]
    if tags_json:
        try:
            data = json.loads(tags_json)
            if isinstance(data, list):
                return [str(tag) for tag in data if str(tag).strip()]
        except json.JSONDecodeError:
            pass
    rows = conn.execute("SELECT tag FROM tags WHERE image_id = ?", (image_id,)).fetchall()
    return [row[0] for row in rows]


def search_by_tags(
    conn: sqlite3.Connection,
    required_tags: Iterable[str],
    limit: int = 2000,
    offset: int = 0,
) -> list[str]:
    tags = list(required_tags)
    if not tags:
        return []
    placeholders = ", ".join("?" for _ in tags)
    query = f"""
        SELECT images.path
        FROM images
        JOIN tags ON tags.image_id = images.id
        WHERE tags.tag IN ({placeholders})
        GROUP BY images.id
        HAVING COUNT(DISTINCT tags.tag) = ?
        ORDER BY images.path
        LIMIT ? OFFSET ?
    """
    params = [*tags, len(tags), limit, offset]
    rows = conn.execute(query, params).fetchall()
    return [row[0] for row in rows]
