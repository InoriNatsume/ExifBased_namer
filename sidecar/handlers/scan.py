import multiprocessing as mp
import os

from core.db.query import get_image_meta
from core.db.storage import replace_payloads, replace_tags, upsert_image
from core.utils import iter_image_files

from ..job_manager import JobContext
from ..scan import extract_task


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
            for (
                path,
                mtime,
                size,
                payloads,
                tags_pos,
                tags_neg,
                tags_char,
                tag_rows,
                error,
            ) in pool.imap_unordered(
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
                        tags_pos or [],
                        tags_neg or [],
                        tags_char or [],
                    )
                    replace_tags(conn, image_id, tag_rows or [])
                    replace_payloads(conn, image_id, payloads or [])
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
