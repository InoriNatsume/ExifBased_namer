"""FastAPI server for NAI Tag Classifier."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.db.schema import ensure_schema
from core.db.storage import connect
from server.context import WebJobContext
from sidecar.jobs import (
    handle_build_nais,
    handle_db_stats,
    handle_move,
    handle_preset_import,
    handle_preset_load,
    handle_preset_save,
    handle_preset_db_delete,
    handle_preset_db_get,
    handle_preset_db_list,
    handle_preset_db_save,
    handle_rename,
    handle_resume_clear,
    handle_scan,
    handle_search,
    handle_strip_suffix,
    handle_template_db_delete,
    handle_template_db_get,
    handle_template_db_list,
    handle_template_db_save,
)


# Handler registry (same as sidecar)
HANDLERS = {
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


# Active jobs and their message queues
active_jobs: dict[str, asyncio.Queue] = {}
cancel_flags: set[str] = set()


# Database connection (thread-local)
_db_path = os.environ.get("NAI_DB_PATH") or "data/app.sqlite"
_thread_local = threading.local()


def get_db():
    """Get thread-local database connection."""
    if not hasattr(_thread_local, 'conn') or _thread_local.conn is None:
        Path(_db_path).parent.mkdir(parents=True, exist_ok=True)
        _thread_local.conn = connect(_db_path)
        ensure_schema(_thread_local.conn)
    return _thread_local.conn


def create_new_db_connection():
    """Create a new database connection for worker threads."""
    Path(_db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = connect(_db_path)
    ensure_schema(conn)
    return conn


class JobRequest(BaseModel):
    op: str
    payload: dict = {}


class JobResponse(BaseModel):
    job_id: str
    status: str


# Store event loop reference
_main_loop: asyncio.AbstractEventLoop | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    global _main_loop
    _main_loop = asyncio.get_event_loop()
    yield
    # Cleanup on shutdown (if needed)


app = FastAPI(title="NAI Tag Classifier", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/job")
async def create_job(request: JobRequest) -> JobResponse:
    """Create a new job and return its ID. Connect via WebSocket to receive updates."""
    logger.info(f"[job] Creating job: op={request.op}, payload keys={list(request.payload.keys())}")
    
    if request.op not in HANDLERS:
        logger.error(f"[job] Unknown op: {request.op}")
        return JobResponse(job_id="", status=f"unknown op: {request.op}")
    
    job_id = f"{request.op}-{uuid.uuid4().hex[:8]}"
    message_queue: asyncio.Queue = asyncio.Queue()
    active_jobs[job_id] = message_queue
    logger.info(f"[job] Job created: {job_id}")
    
    # Run handler in background thread
    def run_job():
        logger.info(f"[job] Starting job thread: {job_id}")
        # Create new connection for this thread
        conn = create_new_db_connection()
        
        def emit(msg: dict):
            # Thread-safe emit to async queue
            if _main_loop is not None:
                asyncio.run_coroutine_threadsafe(message_queue.put(msg), _main_loop)
        
        ctx = WebJobContext(
            job_id=job_id,
            payload=request.payload,
            _emit_callback=emit,
        )
        
        # Override is_cancelled to check cancel flag
        ctx.is_cancelled = lambda: job_id in cancel_flags
        
        handler = HANDLERS[request.op]
        start = time.time()
        try:
            logger.info(f"[job] Running handler for {job_id}")
            handler(ctx, conn)
            logger.info(f"[job] Handler completed for {job_id}")
        except Exception as exc:
            logger.exception(f"[job] Handler failed for {job_id}: {exc}")
            ctx.error(job_id, f"job failed: {exc}")
        finally:
            cancel_flags.discard(job_id)
            emit({
                "id": job_id,
                "type": "log",
                "message": f"elapsed={time.time()-start:.2f}s",
            })
            emit({"id": job_id, "type": "done", "completed": True})
            # Close the thread-local connection
            try:
                conn.close()
            except Exception:
                pass
    
    # Start in thread
    thread = threading.Thread(target=run_job, daemon=True)
    thread.start()
    
    return JobResponse(job_id=job_id, status="started")


@app.post("/api/job/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a running job."""
    if job_id in active_jobs:
        cancel_flags.add(job_id)
        return {"status": "cancel requested"}
    return {"status": "job not found"}


@app.websocket("/ws/job/{job_id}")
async def job_websocket(websocket: WebSocket, job_id: str):
    """WebSocket endpoint to receive job updates."""
    await websocket.accept()
    
    if job_id not in active_jobs:
        await websocket.send_json({"error": "job not found"})
        await websocket.close()
        return
    
    queue = active_jobs[job_id]
    
    try:
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(message)
                
                # Clean up on done
                if message.get("type") == "done":
                    break
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        active_jobs.pop(job_id, None)


# Simple API endpoints (non-streaming)
@app.post("/api/simple/{op}")
async def simple_job(op: str, payload: dict = {}) -> dict:
    """Run a simple job synchronously (for quick operations like db_stats, template_db_list)."""
    if op not in HANDLERS:
        return {"error": f"unknown op: {op}"}
    
    results: list[dict] = []
    
    def emit(msg: dict):
        results.append(msg)
    
    ctx = WebJobContext(
        job_id=f"{op}-sync",
        payload=payload,
        _emit_callback=emit,
    )
    
    conn = get_db()
    handler = HANDLERS[op]
    
    try:
        handler(ctx, conn)
    except Exception as exc:
        return {"error": str(exc)}
    
    return {"results": results}


# ============ File System APIs ============

class BrowseRequest(BaseModel):
    path: str = ""
    
class BrowseResponse(BaseModel):
    current: str
    parent: str | None
    items: list[dict]


@app.post("/api/browse")
async def browse_folder(request: BrowseRequest) -> BrowseResponse:
    """Browse folders on the server file system."""
    import os
    
    # Default to user home or drives on Windows
    path = request.path.strip()
    if not path:
        # Windows: list drives
        if os.name == "nt":
            import string
            drives = []
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append({"name": drive, "type": "drive", "path": drive})
            return BrowseResponse(current="", parent=None, items=drives)
        else:
            path = os.path.expanduser("~")
    
    path = os.path.abspath(path)
    
    if not os.path.exists(path):
        return BrowseResponse(current=path, parent=None, items=[])
    
    if not os.path.isdir(path):
        path = os.path.dirname(path)
    
    items = []
    try:
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            try:
                is_dir = os.path.isdir(full)
                items.append({
                    "name": name,
                    "type": "folder" if is_dir else "file",
                    "path": full,
                })
            except PermissionError:
                continue
    except PermissionError:
        pass
    
    parent = os.path.dirname(path)
    if parent == path:  # root
        parent = None
    
    return BrowseResponse(current=path, parent=parent, items=items)


@app.get("/api/select-folder")
async def select_folder():
    """Open native folder selection dialog."""
    import tkinter as tk
    from tkinter import filedialog
    import threading
    
    result = {"path": None}
    
    def show_dialog():
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder = filedialog.askdirectory(title="폴더 선택")
        result["path"] = folder if folder else None
        root.destroy()
    
    # Run in main thread for tkinter
    thread = threading.Thread(target=show_dialog)
    thread.start()
    thread.join(timeout=120)  # 2 min timeout
    
    return {"path": result["path"]}


@app.get("/api/thumbs/{path:path}")
async def get_thumbnail(path: str):
    """Get thumbnail for an image file."""
    from fastapi.responses import FileResponse
    from core.cache.thumbs import ensure_thumbnail
    
    # Decode path
    import urllib.parse
    decoded_path = urllib.parse.unquote(path)
    
    try:
        thumb_path = ensure_thumbnail(decoded_path)
        if thumb_path and os.path.exists(thumb_path):
            return FileResponse(thumb_path, media_type="image/jpeg")
    except Exception:
        pass
    
    # Return 404 or placeholder
    from fastapi.responses import Response
    return Response(status_code=404)


@app.post("/api/preset/parse-file")
async def parse_preset_file(file: UploadFile = File(...)):
    """Parse an uploaded preset file (NAI Style or SD Studio format)."""
    from core.adapters.nais import parse_nais_file
    from core.adapters.legacy import load_sdstudio_preset
    import tempfile
    
    content = await file.read()
    filename = file.filename or "preset.txt"
    
    # Try to detect format and parse
    try:
        # Save to temp file for parsing
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        values = []
        variable_name = Path(filename).stem
        
        # Try NAI Style format first
        if filename.endswith('.nai') or filename.endswith('.txt'):
            try:
                parsed = parse_nais_file(tmp_path)
                if parsed:
                    values = [{"name": k, "tags": list(v)} for k, v in parsed.items()]
            except Exception:
                pass
        
        # Try SD Studio format
        if not values and (filename.endswith('.json') or filename.endswith('.txt')):
            try:
                data = load_sdstudio_preset(tmp_path)
                if data:
                    values = [{"name": k, "tags": list(v)} for k, v in data.items()]
            except Exception:
                pass
        
        # Try direct JSON parsing
        if not values:
            try:
                text = content.decode('utf-8')
                import json
                data = json.loads(text)
                if isinstance(data, dict):
                    if 'values' in data:
                        values = data['values']
                    elif 'presets' in data:
                        values = [{"name": k, "tags": v} for k, v in data['presets'].items()]
                    else:
                        values = [{"name": k, "tags": v if isinstance(v, list) else [v]} 
                                  for k, v in data.items() if k != 'name']
            except Exception:
                pass
        
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        
        return {"variable_name": variable_name, "values": values}
    
    except Exception as e:
        return {"error": str(e), "values": []}


# Serve static files (UI)
WEB_DIR = ROOT_DIR / "viewer-ui" / "dist"
if WEB_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")
    
    @app.get("/")
    async def serve_index():
        return FileResponse(WEB_DIR / "index.html")
    
    @app.get("/{path:path}")
    async def serve_static(path: str):
        file_path = WEB_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(WEB_DIR / "index.html")
else:
    # Development fallback - show test page
    @app.get("/")
    async def serve_dev_index():
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>NAI Tag Classifier - API Test</title>
    <style>
        body { font-family: sans-serif; background: #1a1a1a; color: #eee; padding: 2rem; }
        h1 { color: #44e0a8; }
        pre { background: #2a2a2a; padding: 1rem; border-radius: 8px; overflow-x: auto; }
        button { background: #44e0a8; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; margin: 0.25rem; }
        button:hover { background: #3bc795; }
        #output { margin-top: 1rem; white-space: pre-wrap; }
    </style>
</head>
<body>
    <h1>NAI Tag Classifier API</h1>
    <p>서버가 정상 동작 중입니다. UI 빌드가 필요합니다.</p>
    
    <h2>API 테스트</h2>
    <button onclick="testDbStats()">DB Stats</button>
    <button onclick="testTemplateList()">Template List</button>
    
    <h3>결과:</h3>
    <pre id="output">버튼을 클릭하세요</pre>
    
    <h2>빌드 방법</h2>
    <pre>
cd viewer-ui
npm install
npm run build
    </pre>
    
    <script>
        async function testDbStats() {
            const res = await fetch('/api/simple/db_stats', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({})
            });
            const data = await res.json();
            document.getElementById('output').textContent = JSON.stringify(data, null, 2);
        }
        
        async function testTemplateList() {
            const res = await fetch('/api/simple/template_db_list', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({})
            });
            const data = await res.json();
            document.getElementById('output').textContent = JSON.stringify(data, null, 2);
        }
    </script>
</body>
</html>
        """
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html)


def main():
    import argparse
    import uvicorn
    
    parser = argparse.ArgumentParser(description="NAI Tag Classifier 서버")
    parser.add_argument("--debug", action="store_true", help="디버그 로그 출력")
    parser.add_argument("--port", type=int, default=8000, help="서버 포트 (기본: 8000)")
    args = parser.parse_args()
    
    # 디버그 모드일 때 로그 레벨 변경
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        log_level = "debug"
    else:
        log_level = "warning"
    
    print("=" * 50)
    print("NAI Tag Classifier 서버")
    if args.debug:
        print("(디버그 모드)")
    print("=" * 50)
    print(f"브라우저에서 열기: http://localhost:{args.port}")
    print("종료: Ctrl+C")
    print("=" * 50)
    
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level=log_level)


if __name__ == "__main__":
    main()
