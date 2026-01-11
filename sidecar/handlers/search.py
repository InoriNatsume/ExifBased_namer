from core.match import match_tag_and
from core.normalize import split_novelai_tags
from core.db.query import search_by_tags
from core.utils import iter_image_files

from ..job_manager import JobContext
from .common import load_tags
from .thumbs import apply_thumb_policy, ensure_preview


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
                tags = load_tags(conn, path, include_negative)
                if match_tag_and(required_tags, tags):
                    matches += 1
                    preview = ensure_preview(ctx.payload, path)
                    ctx.emit(
                        {
                            "id": ctx.job_id,
                            "type": "result",
                            "status": "OK",
                            "source": path,
                            "preview": preview,
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
        apply_thumb_policy(ctx.payload)
        return

    results = search_by_tags(conn, required_tags, limit=limit, offset=offset)
    for path in results:
        preview = ensure_preview(ctx.payload, path)
        ctx.emit(
            {
                "id": ctx.job_id,
                "type": "result",
                "status": "OK",
                "source": path,
                "preview": preview,
            }
        )
    ctx.emit({"id": ctx.job_id, "type": "done", "count": len(results)})
    apply_thumb_policy(ctx.payload)
