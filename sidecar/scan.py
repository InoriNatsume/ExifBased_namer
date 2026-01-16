from __future__ import annotations

import os

from core.extract import extract_payloads_from_image
from core.normalize.novelai import normalize_novelai_payload


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def extract_task(args: tuple[str, bool, int | None, int | None]) -> tuple[
    str,
    int | None,
    int | None,
    list[dict] | None,
    list[str] | None,
    list[str] | None,
    list[str] | None,
    list[tuple[str, str | None, int | None]] | None,
    str | None,
]:
    path, include_negative, mtime, size = args
    try:
        if mtime is None or size is None:
            stat = os.stat(path)
            mtime = int(stat.st_mtime)
            size = int(stat.st_size)
        payloads = extract_payloads_from_image(path)

        pos_tags: list[str] = []
        neg_tags: list[str] = []
        char_tags: list[str] = []
        tag_rows: list[tuple[str, str | None, int | None]] = []
        tag_row_keys: set[tuple[str, str | None, int | None]] = set()

        for payload in payloads:
            normalized = normalize_novelai_payload(payload)
            pos_tags.extend(normalized.get("prompt_tags", []) or [])
            neg_tags.extend(normalized.get("negative_prompt_tags", []) or [])

            for item in normalized.get("char_prompt_tags", []) or []:
                if not isinstance(item, dict):
                    continue
                idx = item.get("idx")
                tags = item.get("tags", []) or []
                char_tags.extend(tags)
                for tag in tags:
                    key = (tag, "char", idx if isinstance(idx, int) else None)
                    if key in tag_row_keys:
                        continue
                    tag_rows.append(key)
                    tag_row_keys.add(key)

            for item in normalized.get("char_negative_prompt_tags", []) or []:
                if not isinstance(item, dict):
                    continue
                idx = item.get("idx")
                tags = item.get("tags", []) or []
                neg_tags.extend(tags)
                for tag in tags:
                    key = (tag, "neg", idx if isinstance(idx, int) else None)
                    if key in tag_row_keys:
                        continue
                    tag_rows.append(key)
                    tag_row_keys.add(key)

        pos_tags = _dedupe(pos_tags)
        neg_tags = _dedupe(neg_tags)
        char_tags = _dedupe(char_tags)

        for tag in pos_tags:
            key = (tag, "pos", None)
            if key not in tag_row_keys:
                tag_rows.append(key)
                tag_row_keys.add(key)

        for tag in neg_tags:
            key = (tag, "neg", None)
            if key not in tag_row_keys:
                tag_rows.append(key)
                tag_row_keys.add(key)

        return path, mtime, size, payloads, pos_tags, neg_tags, char_tags, tag_rows, None
    except Exception as exc:
        return path, None, None, None, None, None, None, None, str(exc)
