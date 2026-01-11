from __future__ import annotations

import multiprocessing as mp
import os
from pathlib import Path
import re
import shutil

from core.db.query import (
    count_images,
    count_matches,
    count_tags,
    get_image_meta,
    get_tags_for_path,
    search_by_tags,
)
from core.db.storage import replace_tags, upsert_image
from core.extract import extract_tags_from_image
from core.normalize import split_novelai_tags
from core.match import match_tag_and
from core.runner import build_variable_specs, match_variable_specs
from core.utils import ensure_unique_name, iter_image_files, render_template, sanitize_filename

from .job_manager import JobContext
from .scan import extract_task


def handle_scan(ctx: JobContext, conn) -> None:
    folder = ctx.payload.get("folder")
    include_negative = bool(ctx.payload.get("include_negative", False))
    progress_step = max(1, int(ctx.payload.get("progress_step") or 200))
    commit_step = max(1, int(ctx.payload.get("commit_step") or 200))
    incremental = bool(ctx.payload.get("incremental", False))
    workers = int(ctx.payload.get("workers") or max(1, (os.cpu_count() or 2) - 1))
    workers = max(1, workers)

    if not folder:
        ctx.error(ctx.job_id, "folder is required")
        return

    image_paths = iter_image_files(folder)
    total = len(image_paths)
    processed = 0
    errors = 0

    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "progress",
            "processed": processed,
            "total": total,
            "errors": errors,
        }
    )
    skipped = 0
    written = 0

    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "progress",
            "processed": processed,
            "total": total,
            "errors": errors,
            "skipped": skipped,
        }
    )

    tasks: list[tuple[str, bool, int | None, int | None]] = []
    if incremental:
        for path in image_paths:
            if ctx.is_cancelled():
                ctx.emit({"id": ctx.job_id, "type": "done", "cancelled": True})
                return
            try:
                stat = os.stat(path)
                mtime = int(stat.st_mtime)
                size = int(stat.st_size)
                meta = get_image_meta(conn, path)
                if meta and meta == (mtime, size):
                    skipped += 1
                    processed += 1
                    if processed % progress_step == 0 or processed == total:
                        ctx.emit(
                            {
                                "id": ctx.job_id,
                                "type": "progress",
                                "processed": processed,
                                "total": total,
                                "errors": errors,
                                "skipped": skipped,
                            }
                        )
                    continue
                tasks.append((path, include_negative, mtime, size))
            except Exception as exc:
                errors += 1
                processed += 1
                ctx.emit(
                    {
                        "id": ctx.job_id,
                        "type": "result",
                        "status": "ERROR",
                        "source": path,
                        "message": str(exc),
                    }
                )
                if processed % progress_step == 0 or processed == total:
                    ctx.emit(
                        {
                            "id": ctx.job_id,
                            "type": "progress",
                            "processed": processed,
                            "total": total,
                            "errors": errors,
                            "skipped": skipped,
                        }
                    )
    else:
        tasks = [(path, include_negative, None, None) for path in image_paths]

    if tasks:
        ctx_obj = mp.get_context("spawn")
        chunksize = max(1, len(tasks) // (workers * 4) or 1)
        with ctx_obj.Pool(processes=workers) as pool:
            for path, mtime, size, tags, error in pool.imap_unordered(
                extract_task, tasks, chunksize=chunksize
            ):
                if ctx.is_cancelled():
                    pool.terminate()
                    pool.join()
                    ctx.emit({"id": ctx.job_id, "type": "done", "cancelled": True})
                    return
                if error:
                    errors += 1
                    processed += 1
                    ctx.emit(
                        {
                            "id": ctx.job_id,
                            "type": "result",
                            "status": "ERROR",
                            "source": path,
                            "message": error,
                        }
                    )
                else:
                    image_id = upsert_image(
                        conn,
                        path,
                        int(mtime),
                        int(size),
                        None,
                        tags or [],
                    )
                    replace_tags(conn, image_id, tags or [])
                    written += 1
                    processed += 1
                    if written % commit_step == 0:
                        conn.commit()
                if processed % progress_step == 0 or processed == total:
                    ctx.emit(
                        {
                            "id": ctx.job_id,
                            "type": "progress",
                            "processed": processed,
                            "total": total,
                            "errors": errors,
                            "skipped": skipped,
                        }
                    )

    conn.commit()
    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "done",
            "processed": processed,
            "errors": errors,
            "skipped": skipped,
        }
    )


def _load_variable_specs(payload: dict) -> list[dict]:
    specs = payload.get("variable_specs")
    if isinstance(specs, list):
        return specs
    variables = payload.get("variables")
    if isinstance(variables, list):
        return build_variable_specs(variables)
    return []


def _load_tags(
    conn,
    path: str,
    include_negative: bool,
) -> list[str]:
    tags = get_tags_for_path(conn, path)
    if tags is not None:
        return tags
    return extract_tags_from_image(path, include_negative)


def handle_rename(ctx: JobContext, conn) -> None:
    folder = ctx.payload.get("folder")
    order = ctx.payload.get("order") or []
    template = ctx.payload.get("template") or ""
    prefix_mode = bool(ctx.payload.get("prefix_mode", False))
    dry_run = bool(ctx.payload.get("dry_run", True))
    include_negative = bool(ctx.payload.get("include_negative", False))
    progress_step = max(1, int(ctx.payload.get("progress_step") or 200))

    if not folder:
        ctx.error(ctx.job_id, "folder is required")
        return
    if isinstance(order, str):
        order = [item.strip() for item in order.split(",") if item.strip()]
    if not order:
        ctx.error(ctx.job_id, "order is required")
        return

    variable_specs = _load_variable_specs(ctx.payload)
    if not variable_specs:
        ctx.error(ctx.job_id, "variable_specs or variables is required")
        return
    spec_names = {spec.get("name") for spec in variable_specs}
    missing = [name for name in order if name not in spec_names]
    if missing:
        ctx.error(ctx.job_id, f"unknown variables: {', '.join(missing)}")
        return

    image_paths = iter_image_files(folder)
    total = len(image_paths)
    processed = 0
    errors = 0

    if not template:
        template = "_".join(f"[{key}]" for key in order)

    reserved = {Path(path).name.lower() for path in image_paths}

    for path in image_paths:
        if ctx.is_cancelled():
            ctx.emit({"id": ctx.job_id, "type": "done", "cancelled": True})
            return
        try:
            tags = _load_tags(conn, path, include_negative)
            matches = match_variable_specs(variable_specs, tags)
        except Exception as exc:
            errors += 1
            processed += 1
            ctx.emit(
                {
                    "id": ctx.job_id,
                    "type": "result",
                    "status": "ERROR",
                    "source": path,
                    "message": str(exc),
                }
            )
            if processed % progress_step == 0 or processed == total:
                ctx.emit(
                    {
                        "id": ctx.job_id,
                        "type": "progress",
                        "processed": processed,
                        "total": total,
                        "errors": errors,
                    }
                )
            continue

        status = "OK"
        values_map: dict[str, str] = {}
        for key in order:
            match = matches.get(key)
            if not match or match.get("status") != "OK":
                status = (
                    "CONFLICT"
                    if match and match.get("status") == "CONFLICT"
                    else "UNKNOWN"
                )
                break
            values_map[key] = match.get("values", [""])[0]

        if status != "OK":
            processed += 1
            ctx.emit(
                {
                    "id": ctx.job_id,
                    "type": "result",
                    "status": status,
                    "source": path,
                    "target": None,
                    "message": None,
                }
            )
            if processed % progress_step == 0 or processed == total:
                ctx.emit(
                    {
                        "id": ctx.job_id,
                        "type": "progress",
                        "processed": processed,
                        "total": total,
                        "errors": errors,
                    }
                )
            continue

        base_name = render_template(template, values_map)
        base_name = sanitize_filename(base_name)
        if prefix_mode:
            stem = Path(path).stem
            if base_name:
                joiner = "" if base_name.endswith("_") else "_"
                base_name = f"{base_name}{joiner}{stem}"
            else:
                base_name = stem

        ext = Path(path).suffix
        new_name = ensure_unique_name(Path(path).parent, base_name, ext, reserved)
        target = str(Path(path).with_name(new_name))
        if not dry_run and target != path:
            try:
                os.rename(path, target)
            except Exception as exc:
                errors += 1
                processed += 1
                ctx.emit(
                    {
                        "id": ctx.job_id,
                        "type": "result",
                        "status": "ERROR",
                        "source": path,
                        "message": str(exc),
                    }
                )
                if processed % progress_step == 0 or processed == total:
                    ctx.emit(
                        {
                            "id": ctx.job_id,
                            "type": "progress",
                            "processed": processed,
                            "total": total,
                            "errors": errors,
                        }
                    )
                continue

        processed += 1
        ctx.emit(
            {
                "id": ctx.job_id,
                "type": "result",
                "status": "OK",
                "source": path,
                "target": target,
                "message": None,
            }
        )
        if processed % progress_step == 0 or processed == total:
            ctx.emit(
                {
                    "id": ctx.job_id,
                    "type": "progress",
                    "processed": processed,
                    "total": total,
                    "errors": errors,
                }
            )

    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "done",
            "processed": processed,
            "errors": errors,
        }
    )


def handle_move(ctx: JobContext, conn) -> None:
    folder = ctx.payload.get("folder")
    variable_name = ctx.payload.get("variable_name") or ""
    template = ctx.payload.get("template") or "[value]"
    target_root = ctx.payload.get("target_root") or ""
    dry_run = bool(ctx.payload.get("dry_run", True))
    include_negative = bool(ctx.payload.get("include_negative", False))
    progress_step = max(1, int(ctx.payload.get("progress_step") or 200))

    if not folder:
        ctx.error(ctx.job_id, "folder is required")
        return
    if not variable_name:
        ctx.error(ctx.job_id, "variable_name is required")
        return
    if not target_root:
        ctx.error(ctx.job_id, "target_root is required")
        return

    variable_specs = _load_variable_specs(ctx.payload)
    if not variable_specs:
        ctx.error(ctx.job_id, "variable_specs or variables is required")
        return
    spec_names = {spec.get("name") for spec in variable_specs}
    if variable_name not in spec_names:
        ctx.error(ctx.job_id, f"unknown variable_name: {variable_name}")
        return

    image_paths = iter_image_files(folder)
    total = len(image_paths)
    processed = 0
    errors = 0
    reserved_map: dict[str, set[str]] = {}

    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "progress",
            "processed": processed,
            "total": total,
            "errors": errors,
        }
    )

    for path in image_paths:
        if ctx.is_cancelled():
            ctx.emit({"id": ctx.job_id, "type": "done", "cancelled": True})
            return
        try:
            tags = _load_tags(conn, path, include_negative)
            matches = match_variable_specs(variable_specs, tags)
        except Exception as exc:
            errors += 1
            processed += 1
            ctx.emit(
                {
                    "id": ctx.job_id,
                    "type": "result",
                    "status": "ERROR",
                    "source": path,
                    "message": str(exc),
                }
            )
            if processed % progress_step == 0 or processed == total:
                ctx.emit(
                    {
                        "id": ctx.job_id,
                        "type": "progress",
                        "processed": processed,
                        "total": total,
                        "errors": errors,
                    }
                )
            continue

        match = matches.get(variable_name, {})
        status = match.get("status") or "UNKNOWN"

        if status != "OK":
            processed += 1
            ctx.emit(
                {
                    "id": ctx.job_id,
                    "type": "result",
                    "status": status,
                    "source": path,
                    "target": None,
                    "message": None,
                }
            )
            if processed % progress_step == 0 or processed == total:
                ctx.emit(
                    {
                        "id": ctx.job_id,
                        "type": "progress",
                        "processed": processed,
                        "total": total,
                        "errors": errors,
                    }
                )
            continue

        value_name = match.get("values", [""])[0]
        folder_name = render_template(template, {"value": value_name})
        folder_name = sanitize_filename(folder_name)
        if not folder_name:
            errors += 1
            processed += 1
            ctx.emit(
                {
                    "id": ctx.job_id,
                    "type": "result",
                    "status": "ERROR",
                    "source": path,
                    "message": "empty folder name",
                }
            )
            if processed % progress_step == 0 or processed == total:
                ctx.emit(
                    {
                        "id": ctx.job_id,
                        "type": "progress",
                        "processed": processed,
                        "total": total,
                        "errors": errors,
                    }
                )
            continue

        target_folder = str(Path(target_root) / folder_name)
        if target_folder not in reserved_map:
            try:
                names = {
                    p.name.lower()
                    for p in Path(target_folder).glob("*")
                    if p.is_file()
                }
            except FileNotFoundError:
                names = set()
            reserved_map[target_folder] = names

        reserved = reserved_map[target_folder]
        ext = Path(path).suffix
        base = Path(path).stem
        new_name = ensure_unique_name(target_folder, base, ext, reserved)
        target = str(Path(target_folder) / new_name)

        if not dry_run:
            Path(target_folder).mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(path, target)
            except Exception as exc:
                errors += 1
                processed += 1
                ctx.emit(
                    {
                        "id": ctx.job_id,
                        "type": "result",
                        "status": "ERROR",
                        "source": path,
                        "message": str(exc),
                    }
                )
                if processed % progress_step == 0 or processed == total:
                    ctx.emit(
                        {
                            "id": ctx.job_id,
                            "type": "progress",
                            "processed": processed,
                            "total": total,
                            "errors": errors,
                        }
                    )
                continue

        processed += 1
        ctx.emit(
            {
                "id": ctx.job_id,
                "type": "result",
                "status": "OK",
                "source": path,
                "target": target,
                "message": None,
            }
        )
        if processed % progress_step == 0 or processed == total:
            ctx.emit(
                {
                    "id": ctx.job_id,
                    "type": "progress",
                    "processed": processed,
                    "total": total,
                    "errors": errors,
                }
            )

    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "done",
            "processed": processed,
            "errors": errors,
        }
    )


_STRIP_RE = re.compile(r"^(?P<base>.+)@@@\\d+$")


def handle_strip_suffix(ctx: JobContext, conn) -> None:
    folder = ctx.payload.get("folder")
    dry_run = bool(ctx.payload.get("dry_run", True))
    progress_step = max(1, int(ctx.payload.get("progress_step") or 200))

    if not folder:
        ctx.error(ctx.job_id, "folder is required")
        return

    image_paths = iter_image_files(folder)
    total = len(image_paths)
    processed = 0
    errors = 0
    skipped = 0
    reserved = {Path(path).name.lower() for path in image_paths}

    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "progress",
            "processed": processed,
            "total": total,
            "errors": errors,
            "skipped": skipped,
        }
    )

    for path in image_paths:
        if ctx.is_cancelled():
            ctx.emit({"id": ctx.job_id, "type": "done", "cancelled": True})
            return
        stem = Path(path).stem
        match = _STRIP_RE.match(stem)
        if not match:
            skipped += 1
            processed += 1
            ctx.emit(
                {
                    "id": ctx.job_id,
                    "type": "result",
                    "status": "SKIP",
                    "source": path,
                    "target": None,
                    "message": None,
                }
            )
            if processed % progress_step == 0 or processed == total:
                ctx.emit(
                    {
                        "id": ctx.job_id,
                        "type": "progress",
                        "processed": processed,
                        "total": total,
                        "errors": errors,
                        "skipped": skipped,
                    }
                )
            continue

        base = match.group("base")
        ext = Path(path).suffix
        candidate = f"{base}{ext}"
        candidate_lower = candidate.lower()
        if candidate_lower in reserved and candidate_lower != Path(path).name.lower():
            errors += 1
            processed += 1
            ctx.emit(
                {
                    "id": ctx.job_id,
                    "type": "result",
                    "status": "ERROR",
                    "source": path,
                    "target": None,
                    "message": "target exists",
                }
            )
            if processed % progress_step == 0 or processed == total:
                ctx.emit(
                    {
                        "id": ctx.job_id,
                        "type": "progress",
                        "processed": processed,
                        "total": total,
                        "errors": errors,
                        "skipped": skipped,
                    }
                )
            continue

        target = str(Path(path).with_name(candidate))
        if not dry_run and target != path:
            try:
                os.rename(path, target)
            except Exception as exc:
                errors += 1
                processed += 1
                ctx.emit(
                    {
                        "id": ctx.job_id,
                        "type": "result",
                        "status": "ERROR",
                        "source": path,
                        "target": None,
                        "message": str(exc),
                    }
                )
                if processed % progress_step == 0 or processed == total:
                    ctx.emit(
                        {
                            "id": ctx.job_id,
                            "type": "progress",
                            "processed": processed,
                            "total": total,
                            "errors": errors,
                            "skipped": skipped,
                        }
                    )
                continue

        reserved.add(candidate_lower)
        processed += 1
        ctx.emit(
            {
                "id": ctx.job_id,
                "type": "result",
                "status": "OK",
                "source": path,
                "target": target,
                "message": None,
            }
        )
        if processed % progress_step == 0 or processed == total:
            ctx.emit(
                {
                    "id": ctx.job_id,
                    "type": "progress",
                    "processed": processed,
                    "total": total,
                    "errors": errors,
                    "skipped": skipped,
                }
            )

    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "done",
            "processed": processed,
            "errors": errors,
            "skipped": skipped,
        }
    )


def handle_search(ctx: JobContext, conn) -> None:
    tags_input = ctx.payload.get("tags") or ""
    limit = int(ctx.payload.get("limit") or 2000)
    offset = int(ctx.payload.get("offset") or 0)
    folder = ctx.payload.get("folder")
    include_negative = bool(ctx.payload.get("include_negative", False))
    progress_step = max(1, int(ctx.payload.get("progress_step") or 200))
    required_tags = split_novelai_tags(tags_input)
    if not required_tags:
        ctx.error(ctx.job_id, "tags is required")
        return

    if folder:
        image_paths = iter_image_files(folder)
        total = len(image_paths)
        processed = 0
        errors = 0
        matches = 0
        ctx.emit(
            {
                "id": ctx.job_id,
                "type": "progress",
                "processed": processed,
                "total": total,
                "errors": errors,
            }
        )
        for path in image_paths:
            if ctx.is_cancelled():
                ctx.emit({"id": ctx.job_id, "type": "done", "cancelled": True})
                return
            try:
                tags = _load_tags(conn, path, include_negative)
                if match_tag_and(required_tags, tags):
                    matches += 1
                    ctx.emit(
                        {
                            "id": ctx.job_id,
                            "type": "result",
                            "status": "OK",
                            "source": path,
                        }
                    )
            except Exception as exc:
                errors += 1
                ctx.emit(
                    {
                        "id": ctx.job_id,
                        "type": "result",
                        "status": "ERROR",
                        "source": path,
                        "message": str(exc),
                    }
                )
            processed += 1
            if processed % progress_step == 0 or processed == total:
                ctx.emit(
                    {
                        "id": ctx.job_id,
                        "type": "progress",
                        "processed": processed,
                        "total": total,
                        "errors": errors,
                    }
                )
        ctx.emit(
            {
                "id": ctx.job_id,
                "type": "done",
                "processed": processed,
                "errors": errors,
                "matches": matches,
            }
        )
        return

    results = search_by_tags(conn, required_tags, limit=limit, offset=offset)
    for path in results:
        ctx.emit({"id": ctx.job_id, "type": "result", "status": "OK", "source": path})
    ctx.emit({"id": ctx.job_id, "type": "done", "count": len(results)})


def handle_db_stats(ctx: JobContext, conn) -> None:
    stats = {
        "images": count_images(conn),
        "tags": count_tags(conn),
        "matches": count_matches(conn),
    }
    ctx.emit({"id": ctx.job_id, "type": "done", "stats": stats})
