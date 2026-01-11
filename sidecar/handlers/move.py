import shutil
from pathlib import Path
from typing import TextIO

from core.runner import match_variable_specs
from core.utils import ensure_unique_name, iter_image_files, render_template, sanitize_filename

from ..job_manager import JobContext
from .common import load_tags, load_variable_specs
from .thumbs import apply_thumb_policy, ensure_preview


def handle_move(ctx: JobContext, conn) -> None:
    folder = ctx.payload.get("folder")
    variable_name = ctx.payload.get("variable_name") or ""
    template = ctx.payload.get("template") or "[value]"
    target_root = ctx.payload.get("target_root") or ""
    dry_run = bool(ctx.payload.get("dry_run", True))
    include_negative = bool(ctx.payload.get("include_negative", False))
    progress_step = max(1, int(ctx.payload.get("progress_step") or 200))
    resume_mode = bool(ctx.payload.get("resume_mode", False))
    resume_path = ctx.payload.get("resume_path")
    checkpoint_step = max(1, int(ctx.payload.get("checkpoint_step") or 200))

    if not folder:
        ctx.error(ctx.job_id, "folder is required")
        return
    if not variable_name:
        ctx.error(ctx.job_id, "variable_name is required")
        return
    if not target_root:
        ctx.error(ctx.job_id, "target_root is required")
        return

    variable_specs = load_variable_specs(ctx.payload)
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
    skipped = 0
    resume_written = 0
    resume_file: TextIO | None = None
    resume_done: set[str] = set()
    reserved_map: dict[str, set[str]] = {}

    if not resume_path:
        resume_path = str(Path(folder) / ".nai_resume_move.txt")
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

            match = matches.get(variable_name, {})
            status = match.get("status") or "UNKNOWN"

            if status != "OK":
                processed += 1
                preview = ensure_preview(ctx.payload, path)
                ctx.emit(
                    {
                        "id": ctx.job_id,
                        "type": "result",
                        "status": status,
                        "source": path,
                        "target": None,
                        "message": None,
                        "preview": preview,
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
            preview_source = path if dry_run else target
            preview = ensure_preview(ctx.payload, preview_source)
            ctx.emit(
                {
                    "id": ctx.job_id,
                    "type": "result",
                    "status": "OK",
                    "source": path,
                    "target": target,
                    "message": None,
                    "preview": preview,
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
    apply_thumb_policy(ctx.payload)
