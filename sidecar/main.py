import json
import multiprocessing as mp
import os
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.db.schema import ensure_schema
from core.db.storage import connect
from sidecar.emitter import JsonEmitter
from sidecar.job_manager import Job, JobManager
from sidecar.jobs import (
    handle_build_nais,
    handle_db_stats,
    handle_move,
    handle_rename,
    handle_resume_clear,
    handle_scan,
    handle_search,
    handle_strip_suffix,
    handle_preset_import,
    handle_preset_load,
    handle_preset_save,
    handle_preset_db_delete,
    handle_preset_db_get,
    handle_preset_db_list,
    handle_preset_db_save,
    handle_template_db_delete,
    handle_template_db_get,
    handle_template_db_list,
    handle_template_db_save,
)


def main() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    mp.freeze_support()
    db_path = os.environ.get("NAI_DB_PATH") or "data/app.sqlite"
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    emitter = JsonEmitter()
    handlers = {
        "scan": handle_scan,
        "search": handle_search,
        "db_stats": handle_db_stats,
        "rename": handle_rename,
        "resume_clear": handle_resume_clear,
        "move": handle_move,
        "strip_suffix": handle_strip_suffix,
        "build_nais": handle_build_nais,
        "preset_load": handle_preset_load,
        "preset_save": handle_preset_save,
        "preset_import": handle_preset_import,
        "template_db_list": handle_template_db_list,
        "template_db_get": handle_template_db_get,
        "template_db_save": handle_template_db_save,
        "template_db_delete": handle_template_db_delete,
        "preset_db_list": handle_preset_db_list,
        "preset_db_get": handle_preset_db_get,
        "preset_db_save": handle_preset_db_save,
        "preset_db_delete": handle_preset_db_delete,
    }

    def _make_conn():
        conn = connect(db_path)
        ensure_schema(conn)
        return conn

    manager = JobManager(handlers, emitter, _make_conn)
    manager.start()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            emitter.error(None, f"invalid json: {exc}")
            continue

        msg_type = message.get("type")
        job_id = message.get("id")
        if msg_type == "cancel" and job_id:
            manager.cancel(job_id)
            continue

        if msg_type != "run":
            emitter.error(job_id, "invalid message type")
            continue

        op = message.get("op")
        payload = message.get("payload") or {}
        if not job_id:
            emitter.error(None, "job id is required")
            continue
        if op not in handlers:
            emitter.error(job_id, f"unknown op: {op}")
            continue
        emitter.emit({"id": job_id, "type": "ack", "op": op})
        manager.submit(Job(job_id=job_id, op=op, payload=payload))

    manager.wait_all()
    manager.stop()


if __name__ == "__main__":
    main()
