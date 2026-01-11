from __future__ import annotations

import os

from core.extract import extract_tags_from_image


def extract_task(args: tuple[str, bool, int | None, int | None]) -> tuple[
    str, int | None, int | None, list[str] | None, str | None
]:
    path, include_negative, mtime, size = args
    try:
        if mtime is None or size is None:
            stat = os.stat(path)
            mtime = int(stat.st_mtime)
            size = int(stat.st_size)
        tags = extract_tags_from_image(path, include_negative)
        return path, mtime, size, tags, None
    except Exception as exc:
        return path, None, None, None, str(exc)
