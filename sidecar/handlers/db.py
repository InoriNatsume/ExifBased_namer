from core.db.query import count_images, count_matches, count_tags

from ..job_manager import JobContext


def handle_db_stats(ctx: JobContext, conn) -> None:
    stats = {
        "images": count_images(conn),
        "tags": count_tags(conn),
        "matches": count_matches(conn),
    }
    ctx.emit({"id": ctx.job_id, "type": "done", "stats": stats})
