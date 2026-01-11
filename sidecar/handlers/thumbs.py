import os
from pathlib import Path

from core.cache import ensure_thumbnail, prune_cache, resolve_cache_dir


def _parse_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _env_int(key: str) -> int | None:
    return _parse_int(os.environ.get(key))


def _thumbs_enabled(payload: dict) -> bool:
    return bool(payload.get("thumbs", False))


def ensure_preview(payload: dict, path: str) -> str | None:
    if not _thumbs_enabled(payload):
        return None

    cache_dir = payload.get("thumb_cache_dir") or os.environ.get("NAI_CACHE_DIR")
    size = _parse_int(payload.get("thumb_size")) or _env_int("NAI_CACHE_THUMB_SIZE") or 256
    quality = (
        _parse_int(payload.get("thumb_quality"))
        or _env_int("NAI_CACHE_THUMB_QUALITY")
        or 85
    )
    result = ensure_thumbnail(path, cache_dir, size=size, quality=quality)
    return str(result) if result else None


def apply_thumb_policy(payload: dict) -> int:
    if not _thumbs_enabled(payload):
        return 0

    max_files = _parse_int(payload.get("thumb_max_files")) or _env_int("NAI_CACHE_MAX_FILES")
    max_bytes = _parse_int(payload.get("thumb_max_bytes")) or _env_int("NAI_CACHE_MAX_BYTES")
    if max_files is None and max_bytes is None:
        return 0

    cache_dir = payload.get("thumb_cache_dir") or os.environ.get("NAI_CACHE_DIR")
    if cache_dir:
        resolve_cache_dir(Path(str(cache_dir)))
    return prune_cache(cache_dir, max_files=max_files, max_bytes=max_bytes)
