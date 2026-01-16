"""Web-compatible JobContext for FastAPI handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
import asyncio


@dataclass
class WebJobContext:
    """JobContext compatible with existing handlers, but emits via callback."""

    job_id: str
    payload: dict
    _emit_callback: Callable[[dict], None]
    _cancelled: bool = field(default=False, repr=False)

    def emit(self, message: dict) -> None:
        """Emit a message (progress/result/done/log)."""
        self._emit_callback(message)

    def error(self, job_id: str | None, message: str) -> None:
        """Emit an error message."""
        self._emit_callback({
            "id": job_id or self.job_id,
            "type": "error",
            "message": message,
        })

    def is_cancelled(self) -> bool:
        """Check if the job was cancelled."""
        return self._cancelled

    def clear_cancel(self) -> None:
        """Clear the cancel flag."""
        self._cancelled = False

    def cancel(self) -> None:
        """Set the cancel flag."""
        self._cancelled = True
