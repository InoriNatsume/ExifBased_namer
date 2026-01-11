from __future__ import annotations

from dataclasses import dataclass
import queue
import threading
import time
from typing import Callable


@dataclass
class Job:
    job_id: str
    op: str
    payload: dict


@dataclass
class JobContext:
    job_id: str
    payload: dict
    emit: Callable[[dict], None]
    error: Callable[[str | None, str], None]
    is_cancelled: Callable[[], bool]
    clear_cancel: Callable[[], None]


class JobManager:
    def __init__(
        self,
        handlers: dict[str, Callable[[JobContext, object], None]],
        emitter,
        conn_factory: Callable[[], object],
    ) -> None:
        self._handlers = handlers
        self._emit = emitter.emit
        self._error = emitter.error
        self._conn_factory = conn_factory
        self._queue: queue.Queue[Job | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._stop_event = threading.Event()
        self._cancel_flags: set[str] = set()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._queue.put(None)
        self._thread.join()

    def wait_all(self) -> None:
        self._queue.join()

    def submit(self, job: Job) -> None:
        self._queue.put(job)

    def cancel(self, job_id: str) -> None:
        self._cancel_flags.add(job_id)

    def _run(self) -> None:
        conn = self._conn_factory()
        try:
            while not self._stop_event.is_set():
                job = self._queue.get()
                if job is None:
                    self._queue.task_done()
                    break
                handler = self._handlers.get(job.op)
                if handler is None:
                    self._error(job.job_id, f"unknown op: {job.op}")
                    self._queue.task_done()
                    continue
                ctx = JobContext(
                    job_id=job.job_id,
                    payload=job.payload,
                    emit=self._emit,
                    error=self._error,
                    is_cancelled=lambda: job.job_id in self._cancel_flags,
                    clear_cancel=lambda: self._cancel_flags.discard(job.job_id),
                )
                start = time.time()
                try:
                    handler(ctx, conn)
                except Exception as exc:
                    self._error(job.job_id, f"job failed: {exc}")
                finally:
                    ctx.clear_cancel()
                    self._emit(
                        {
                            "id": job.job_id,
                            "type": "log",
                            "message": f"elapsed={time.time()-start:.2f}s",
                        }
                    )
                    self._queue.task_done()
        finally:
            conn.close()
