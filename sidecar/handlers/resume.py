from pathlib import Path

from ..job_manager import JobContext


def handle_resume_clear(ctx: JobContext, _conn) -> None:
    folder = ctx.payload.get("folder")
    kind = ctx.payload.get("kind") or "rename"
    path = ctx.payload.get("path")

    if path:
        target = Path(str(path))
    else:
        if not folder:
            ctx.error(ctx.job_id, "folder is required")
            return
        suffix = ".nai_resume_move.txt" if kind == "move" else ".nai_resume_rename.txt"
        target = Path(str(folder)) / suffix

    removed = False
    if target.exists():
        try:
            target.unlink()
            removed = True
        except Exception as exc:
            ctx.error(ctx.job_id, f"failed to remove resume file: {exc}")
            return

    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "done",
            "payload": {"path": str(target), "removed": removed},
        }
    )
