import json
import threading


class JsonEmitter:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def emit(self, payload: dict) -> None:
        with self._lock:
            print(json.dumps(payload, ensure_ascii=False), flush=True)

    def error(self, job_id: str | None, message: str) -> None:
        payload = {"type": "error", "message": message}
        if job_id:
            payload["id"] = job_id
        self.emit(payload)
