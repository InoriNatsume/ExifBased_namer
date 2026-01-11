from __future__ import annotations

import json
import locale
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Callable


def _next_job_id(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000)}"


def _decode_line(raw: bytes) -> str:
    encodings = ("utf-8", locale.getpreferredencoding(False), "cp949")
    for encoding in encodings:
        if not encoding:
            continue
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def run_sidecar_job(
    op: str,
    payload: dict,
    on_message: Callable[[dict], None],
    job_id: str | None = None,
) -> None:
    root_dir = Path(__file__).resolve().parents[1]
    sidecar_path = root_dir / "sidecar" / "main.py"
    job_id = job_id or _next_job_id(op)
    message = {"id": job_id, "type": "run", "op": op, "payload": payload}

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    proc = subprocess.Popen(
        [sys.executable, str(sidecar_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=str(root_dir),
    )

    def _drain_stderr() -> None:
        if not proc.stderr:
            return
        for raw in proc.stderr:
            line = _decode_line(raw).strip()
            if line:
                on_message({"type": "log", "message": line})

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    if proc.stdin:
        payload = json.dumps(message, ensure_ascii=False) + "\n"
        proc.stdin.write(payload.encode("utf-8"))
        proc.stdin.flush()
        proc.stdin.close()

    if proc.stdout:
        for raw in proc.stdout:
            line = _decode_line(raw).strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                on_message({"type": "error", "message": f"invalid json: {line}"})
                continue
            on_message(parsed)

    return_code = proc.wait()
    if return_code != 0:
        on_message({"type": "error", "message": f"sidecar exited: {return_code}"})
