from __future__ import annotations

import sqlite3
import json
from typing import Iterable


_SCHEMA_FLAGS: dict[int, dict[str, bool]] = {}


def _get_schema_flags(conn: sqlite3.Connection) -> dict[str, bool]:
    key = id(conn)
    cached = _SCHEMA_FLAGS.get(key)
    if cached:
        return cached

    flags = {"tags_source": False, "images_split_tags": False}
    try:
        tags_cols = {row[1] for row in conn.execute("PRAGMA table_info(tags)").fetchall()}
        flags["tags_source"] = "source_type" in tags_cols
    except sqlite3.Error:
        flags["tags_source"] = False
    try:
        image_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(images)").fetchall()
        }
        flags["images_split_tags"] = (
            "tags_pos_json" in image_cols
            and "tags_neg_json" in image_cols
            and "tags_char_json" in image_cols
        )
    except sqlite3.Error:
        flags["images_split_tags"] = False

    _SCHEMA_FLAGS[key] = flags
    return flags


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


def _parse_tag_json(text: str | None) -> list[str]:
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [str(tag) for tag in data if str(tag).strip()]
    return []


def get_tags_for_path(
    conn: sqlite3.Connection,
    path: str,
    include_negative: bool = False,
) -> list[str] | None:
    flags = _get_schema_flags(conn)
    if flags.get("images_split_tags"):
        row = conn.execute(
            "SELECT id, tags_pos_json, tags_neg_json, tags_char_json, tags_json FROM images WHERE path = ?",
            (path,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id, tags_json FROM images WHERE path = ?",
            (path,),
        ).fetchone()
    if not row:
        return None
    image_id = int(row[0])

    if flags.get("images_split_tags"):
        tags = []
        tags.extend(_parse_tag_json(row[1]))
        tags.extend(_parse_tag_json(row[3]))
        if include_negative:
            tags.extend(_parse_tag_json(row[2]))
        if tags:
            return tags
        tags = _parse_tag_json(row[4]) if len(row) > 4 else []
        if tags:
            return tags
    else:
        if len(row) > 1:
            tags = _parse_tag_json(row[1])
            if tags:
                return tags

    if flags.get("tags_source"):
        if include_negative:
            rows = conn.execute(
                "SELECT tag FROM tags WHERE image_id = ?",
                (image_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT tag FROM tags WHERE image_id = ? AND (source_type IS NULL OR source_type IN ('pos','char'))",
                (image_id,),
            ).fetchall()
    else:
        rows = conn.execute("SELECT tag FROM tags WHERE image_id = ?", (image_id,)).fetchall()
    return [row[0] for row in rows]


def search_by_tags(
    conn: sqlite3.Connection,
    required_tags: Iterable[str],
    *,
    include_negative: bool = False,
    limit: int = 2000,
    offset: int = 0,
) -> list[str]:
    tags = list(required_tags)
    if not tags:
        return []
    placeholders = ", ".join("?" for _ in tags)
    flags = _get_schema_flags(conn)
    if flags.get("tags_source") and not include_negative:
        source_filter = "AND (tags.source_type IS NULL OR tags.source_type IN ('pos','char'))"
    else:
        source_filter = ""
    query = f"""
        SELECT images.path
        FROM images
        JOIN tags ON tags.image_id = images.id
        WHERE tags.tag IN ({placeholders})
        {source_filter}
        GROUP BY images.id
        HAVING COUNT(DISTINCT tags.tag) = ?
        ORDER BY images.path
        LIMIT ? OFFSET ?
    """
    params = [*tags, len(tags), limit, offset]
    rows = conn.execute(query, params).fetchall()
    return [row[0] for row in rows]


def list_templates(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name, updated_at FROM templates ORDER BY updated_at DESC"
    ).fetchall()
    return [{"id": int(row[0]), "name": row[1], "updated_at": row[2]} for row in rows]


def get_template(
    conn: sqlite3.Connection, *, template_id: int | None = None, name: str | None = None
) -> dict | None:
    if template_id is not None:
        row = conn.execute(
            "SELECT id, name, payload_json, updated_at FROM templates WHERE id = ?",
            (template_id,),
        ).fetchone()
    elif name:
        row = conn.execute(
            "SELECT id, name, payload_json, updated_at FROM templates WHERE name = ?",
            (name,),
        ).fetchone()
    else:
        return None
    if not row:
        return None
    return {
        "id": int(row[0]),
        "name": row[1],
        "payload": json.loads(row[2]),
        "updated_at": row[3],
    }


def list_presets(
    conn: sqlite3.Connection,
    *,
    source_kind: str | None = None,
    variable_name: str | None = None,
) -> list[dict]:
    params: list[object] = []
    clauses: list[str] = []
    if source_kind:
        clauses.append("source_kind = ?")
        params.append(source_kind)
    if variable_name:
        clauses.append("variable_name = ?")
        params.append(variable_name)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""
        SELECT id, name, source_kind, variable_name, updated_at
        FROM presets
        {where}
        ORDER BY updated_at DESC
        """,
        params,
    ).fetchall()
    return [
        {
            "id": int(row[0]),
            "name": row[1],
            "source_kind": row[2],
            "variable_name": row[3],
            "updated_at": row[4],
        }
        for row in rows
    ]


def get_preset(conn: sqlite3.Connection, preset_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, name, source_kind, variable_name, payload_json, updated_at FROM presets WHERE id = ?",
        (preset_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": int(row[0]),
        "name": row[1],
        "source_kind": row[2],
        "variable_name": row[3],
        "payload": json.loads(row[4]),
        "updated_at": row[5],
    }
