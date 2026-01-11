from core.adapters.nais import import_nais_payload
from nais_builder.builder import build_nais_from_folder

from ..job_manager import JobContext


def handle_build_nais(ctx: JobContext, conn) -> None:
    folder = ctx.payload.get("folder")
    include_negative = bool(ctx.payload.get("include_negative", False))
    progress_step = max(1, int(ctx.payload.get("progress_step") or 200))

    if not folder:
        ctx.error(ctx.job_id, "folder is required")
        return

    def _progress(processed: int, total: int) -> None:
        ctx.emit(
            {
                "id": ctx.job_id,
                "type": "progress",
                "processed": processed,
                "total": total,
                "errors": 0,
            }
        )

    payload, stats = build_nais_from_folder(
        folder,
        include_negative=include_negative,
        progress_step=progress_step,
        progress_cb=_progress,
    )
    variable_name, values = import_nais_payload(payload)
    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "done",
            "processed": stats.get("total", 0),
            "errors": 0,
            "payload": {
                "variable_name": variable_name,
                "values": [value.model_dump() for value in values],
                "common_tags": stats.get("common_tags", []),
            },
            "stats": stats,
        }
    )
