import os
from pathlib import Path
import re

from core.utils import iter_image_files

from ..job_manager import JobContext


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
