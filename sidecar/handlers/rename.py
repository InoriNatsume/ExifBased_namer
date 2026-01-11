import os
from pathlib import Path
from typing import TextIO

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
    resume_mode = bool(ctx.payload.get("resume_mode", False))
    resume_path = ctx.payload.get("resume_path")
    checkpoint_step = max(1, int(ctx.payload.get("checkpoint_step") or 200))

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
    skipped = 0
    resume_written = 0
    resume_file: TextIO | None = None
    resume_done: set[str] = set()

    if not resume_path:
        resume_path = str(Path(folder) / ".nai_resume_rename.txt")
    resume_file_path = Path(str(resume_path))
    resume_file_path.parent.mkdir(parents=True, exist_ok=True)
    if resume_mode and resume_file_path.exists():
        try:
            with resume_file_path.open("r", encoding="utf-8") as handle:
                resume_done = {line.strip() for line in handle if line.strip()}
        except Exception:
            resume_done = set()
    else:
        resume_file_path.write_text("", encoding="utf-8")
    resume_file = resume_file_path.open("a", encoding="utf-8")

    if not template:
        template = "_".join(f"[{key}]" for key in order)

    reserved = {Path(path).name.lower() for path in image_paths}

    cancelled = False
    try:
        for path in image_paths:
            if path in resume_done:
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
            if ctx.is_cancelled():
                cancelled = True
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
                            "skipped": skipped,
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
                if resume_file:
                    resume_file.write(f"{path}\n")
                    resume_written += 1
                    if resume_written % checkpoint_step == 0:
                        resume_file.flush()
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
                    if resume_file:
                        resume_file.write(f"{path}\n")
                        resume_written += 1
                        if resume_written % checkpoint_step == 0:
                            resume_file.flush()
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
            if resume_file:
                final_path = path if dry_run else target
                resume_file.write(f"{final_path}\n")
                resume_written += 1
                if resume_written % checkpoint_step == 0:
                    resume_file.flush()
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
    finally:
        if resume_file:
            resume_file.flush()
            resume_file.close()
        if not cancelled:
            resume_file_path.unlink(missing_ok=True)

    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "done",
            "processed": processed,
            "errors": errors,
            "skipped": skipped,
        }
    )
