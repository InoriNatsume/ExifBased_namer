import os
from pathlib import Path

from core.runner import match_variable_specs
from core.utils import ensure_unique_name, iter_image_files, render_template, sanitize_filename

from ..job_manager import JobContext
from .common import load_tags, load_variable_specs


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

    variable_specs = load_variable_specs(ctx.payload)
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
            tags = load_tags(conn, path, include_negative)
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
