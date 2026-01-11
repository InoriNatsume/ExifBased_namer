import logging
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.normalize import split_novelai_tags
from core.utils import format_eta
from gui.result_view import ResultView
from gui.sidecar_client import run_sidecar_job


logger = logging.getLogger(__name__)


class SearchTab:
    def __init__(self, parent: ttk.Frame, app: "RuleEditorApp") -> None:
        self.app = app
        self.folder_var = tk.StringVar()
        self.tags_var = tk.StringVar()
        self.include_negative_var = tk.BooleanVar(value=False)
        self.incremental_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="대기")

        self.queue: queue.Queue | None = None
        self.thread: threading.Thread | None = None
        self.active_op: str | None = None
        self.stats = {"ok": 0, "error": 0}
        self.scan_stats = {"errors": 0, "skipped": 0}
        self.total = 0
        self.processed = 0
        self.start_time = 0.0
        self.result_view: ResultView | None = None

        self._build(parent)

    def _build(self, parent: ttk.Frame) -> None:
        ctrl = ttk.Labelframe(parent, text="검색")
        ctrl.pack(fill=tk.X, padx=10, pady=8)
        ctrl.columnconfigure(1, weight=1)

        ttk.Label(ctrl, text="작업 폴더").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(ctrl, textvariable=self.folder_var, width=60).grid(
            row=0, column=1, sticky="we", padx=6, pady=6
        )
        ttk.Button(ctrl, text="찾기", command=self._select_folder).grid(
            row=0, column=2, padx=6, pady=6
        )

        ttk.Label(ctrl, text="필수 태그").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(ctrl, textvariable=self.tags_var, width=60).grid(
            row=1, column=1, sticky="we", padx=6, pady=6
        )
        self.run_button = ttk.Button(ctrl, text="검색", command=self._run_search)
        self.run_button.grid(row=1, column=2, padx=6, pady=6)

        options = ttk.Frame(ctrl)
        options.grid(row=2, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        ttk.Checkbutton(
            options, text="네거티브 태그 포함", variable=self.include_negative_var
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(options, text="증분 스캔", variable=self.incremental_var).pack(
            side=tk.LEFT
        )

        self.scan_button = ttk.Button(ctrl, text="DB 스캔", command=self._run_scan)
        self.scan_button.grid(row=2, column=2, padx=6, pady=4)

        ttk.Label(ctrl, textvariable=self.status_var).grid(
            row=3, column=0, sticky="w", padx=6, pady=4, columnspan=3
        )
        ttk.Label(
            ctrl,
            text=(
                "설명: 검색은 필수 태그 AND 조건입니다. "
                "DB 스캔은 폴더 전체를 읽어 태그를 DB에 저장합니다."
            ),
        ).grid(row=4, column=0, columnspan=3, sticky="w", padx=6, pady=4)

        result_frame = ttk.Labelframe(parent, text="검색 결과")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        self.result_view = ResultView(result_frame, show_filters=True)

    def _select_folder(self) -> None:
        folder = filedialog.askdirectory(title="폴더 선택")
        if folder:
            self.folder_var.set(folder)

    def _run_search(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        folder = self.folder_var.get()
        if not folder:
            messagebox.showwarning("검색", "폴더를 선택하세요.")
            return
        raw_tags = self.tags_var.get()
        required_tags = split_novelai_tags(raw_tags)
        if not required_tags:
            messagebox.showwarning("검색", "필수 태그를 입력하세요.")
            return

        include_negative = bool(self.include_negative_var.get())

        self.active_op = "search"
        self.stats = {"ok": 0, "error": 0}
        self.total = 0
        self.processed = 0
        self.start_time = time.monotonic()
        if self.result_view:
            self.result_view.clear()
        self.status_var.set("검색 준비 중...")
        self.run_button.config(state="disabled")
        self.scan_button.config(state="disabled")

        self.queue = queue.Queue()
        payload = {
            "folder": folder,
            "tags": raw_tags,
            "include_negative": include_negative,
            "progress_step": 200,
        }
        self.thread = threading.Thread(
            target=run_sidecar_job,
            args=("search", payload, self.queue.put),
            daemon=True,
        )
        self.thread.start()
        self.app.root.after(100, self._poll_queue)

    def _run_scan(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        folder = self.folder_var.get()
        if not folder:
            messagebox.showwarning("DB 스캔", "폴더를 선택하세요.")
            return

        include_negative = bool(self.include_negative_var.get())
        incremental = bool(self.incremental_var.get())

        self.active_op = "scan"
        self.scan_stats = {"errors": 0, "skipped": 0}
        self.total = 0
        self.processed = 0
        self.start_time = time.monotonic()
        if self.result_view:
            self.result_view.clear()
        self.status_var.set("DB 스캔 준비 중...")
        self.run_button.config(state="disabled")
        self.scan_button.config(state="disabled")

        self.queue = queue.Queue()
        payload = {
            "folder": folder,
            "include_negative": include_negative,
            "incremental": incremental,
            "progress_step": 200,
            "commit_step": 200,
        }
        self.thread = threading.Thread(
            target=run_sidecar_job,
            args=("scan", payload, self.queue.put),
            daemon=True,
        )
        self.thread.start()
        self.app.root.after(100, self._poll_queue)

    def _poll_queue(self) -> None:
        if not self.queue:
            return
        updated = False
        try:
            while True:
                message = self.queue.get_nowait()
                updated = True
                msg_type = message.get("type")
                if msg_type == "result":
                    status = message.get("status") or "OK"
                    payload = {
                        "source": message.get("source"),
                        "message": message.get("message"),
                    }
                    if self.active_op == "search":
                        record = self._make_record(status, payload)
                        if status == "OK":
                            self.stats["ok"] += 1
                        elif status == "ERROR":
                            self.stats["error"] += 1
                        if self.result_view:
                            self.result_view.add_record(record)
                    elif status == "ERROR":
                        record = self._make_record(status, payload)
                        self.scan_stats["errors"] += 1
                        if self.result_view:
                            self.result_view.add_record(record)
                elif msg_type == "progress":
                    processed = int(message.get("processed") or 0)
                    total = int(message.get("total") or 0)
                    errors = int(message.get("errors") or 0)
                    self.processed = max(self.processed, processed)
                    if total:
                        self.total = total
                    if self.active_op == "search":
                        self.stats["error"] = max(self.stats["error"], errors)
                    else:
                        skipped = int(message.get("skipped") or 0)
                        self.scan_stats["errors"] = max(self.scan_stats["errors"], errors)
                        self.scan_stats["skipped"] = max(
                            self.scan_stats["skipped"], skipped
                        )
                elif msg_type == "done":
                    self.processed = max(self.processed, int(message.get("processed") or 0))
                    if self.active_op == "search":
                        matches = int(message.get("matches") or self.stats["ok"])
                        errors = int(message.get("errors") or self.stats["error"])
                        self.stats["ok"] = matches
                        self.stats["error"] = errors
                        if self.total <= 0:
                            self.total = self.processed
                        self.status_var.set(self._format_status("완료"))
                        logger.info("Search done: %d matched", matches)
                    else:
                        errors = int(message.get("errors") or self.scan_stats["errors"])
                        skipped = int(message.get("skipped") or self.scan_stats["skipped"])
                        self.scan_stats["errors"] = errors
                        self.scan_stats["skipped"] = skipped
                        if self.total <= 0:
                            self.total = self.processed
                        self.status_var.set(self._format_scan_status("완료"))
                        logger.info(
                            "Scan done: processed=%d errors=%d skipped=%d",
                            self.processed,
                            errors,
                            skipped,
                        )
                    self.run_button.config(state="normal")
                    self.scan_button.config(state="normal")
                    return
                elif msg_type == "error":
                    self.run_button.config(state="normal")
                    self.scan_button.config(state="normal")
                    messagebox.showerror("검색", message.get("message") or "error")
                    return
        except queue.Empty:
            pass

        if updated:
            if self.active_op == "search":
                self.status_var.set(self._format_status("진행"))
            else:
                self.status_var.set(self._format_scan_status("진행"))
        self.app.root.after(100, self._poll_queue)

    def _format_status(self, prefix: str) -> str:
        eta = format_eta(self.processed, self.total, self.start_time)
        return (
            f"{prefix}: {self.processed}/{self.total} "
            f"일치 {self.stats['ok']} 오류 {self.stats['error']} ETA {eta}"
        )

    def _format_scan_status(self, prefix: str) -> str:
        eta = format_eta(self.processed, self.total, self.start_time)
        return (
            f"{prefix}: {self.processed}/{self.total} "
            f"오류 {self.scan_stats['errors']} 스킵 {self.scan_stats['skipped']} ETA {eta}"
        )

    def _make_record(self, status: str, payload: dict) -> dict:
        source = payload.get("source")
        message = payload.get("message")
        if status == "OK":
            text = f"OK | {source}"
        elif message:
            text = f"{status} | {source} | {message}"
        else:
            text = f"{status} | {source}"
        return {
            "status": status,
            "text": text,
            "source": source,
            "target": None,
            "preview": source,
        }
