from datetime import datetime
import logging
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.utils import format_eta
from gui.common import open_in_default_app
from gui.result_view import ResultView
from gui.sidecar_client import run_sidecar_job


logger = logging.getLogger(__name__)


class RenameTab:
    def __init__(self, parent: ttk.Frame, app: "RuleEditorApp") -> None:
        self.app = app
        self.state = app.state

        self.source_var = tk.StringVar()
        self.order_var = tk.StringVar()
        self.template_var = tk.StringVar()
        self.prefix_var = tk.BooleanVar(value=False)
        self.dry_run_var = tk.BooleanVar(value=True)
        self.include_negative_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="대기")

        self.queue: queue.Queue | None = None
        self.thread: threading.Thread | None = None
        self.stats = {"ok": 0, "unknown": 0, "conflict": 0, "error": 0}
        self.total = 0
        self.processed = 0
        self.start_time = 0.0
        self.issue_path: str | None = None
        self.issue_handle = None
        self.issue_count = 0

        self.result_view: ResultView | None = None

        self.strip_queue: queue.Queue | None = None
        self.strip_thread: threading.Thread | None = None
        self.strip_stats = {"ok": 0, "skip": 0, "error": 0}
        self.strip_total = 0
        self.strip_processed = 0
        self.strip_start_time = 0.0

        self._build(parent)

    def _build(self, parent: ttk.Frame) -> None:
        ctrl = ttk.Labelframe(parent, text="파일명 변경")
        ctrl.pack(fill=tk.X, padx=10, pady=8)
        ctrl.columnconfigure(1, weight=1)

        ttk.Label(ctrl, text="원본 폴더").grid(
            row=0, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Entry(ctrl, textvariable=self.source_var, width=60).grid(
            row=0, column=1, sticky="we", padx=6, pady=6
        )
        ttk.Button(ctrl, text="찾기", command=self._select_folder).grid(
            row=0, column=2, padx=6, pady=6
        )

        ttk.Label(ctrl, text="변수 순서").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(ctrl, textvariable=self.order_var, width=60).grid(
            row=1, column=1, sticky="we", padx=6, pady=6
        )
        ttk.Checkbutton(ctrl, text="접두사 모드", variable=self.prefix_var).grid(
            row=1, column=2, padx=6, pady=6
        )

        ttk.Label(ctrl, text="템플릿").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(ctrl, textvariable=self.template_var, width=60).grid(
            row=2, column=1, sticky="we", padx=6, pady=6
        )
        ttk.Checkbutton(
            ctrl, text="네거티브 태그 포함", variable=self.include_negative_var
        ).grid(row=2, column=2, padx=6, pady=6)

        options = ttk.Frame(ctrl)
        options.grid(row=3, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        ttk.Checkbutton(options, text="드라이런", variable=self.dry_run_var).pack(
            side=tk.LEFT
        )

        buttons = ttk.Frame(ctrl)
        buttons.grid(row=3, column=2, sticky="e", padx=6, pady=4)
        self.strip_button = ttk.Button(buttons, text="@@@ 제거", command=self._run_strip)
        self.strip_button.pack(side=tk.LEFT, padx=(0, 6))
        self.run_button = ttk.Button(buttons, text="실행", command=self._run)
        self.run_button.pack(side=tk.LEFT)

        ttk.Label(ctrl, textvariable=self.status_var).grid(
            row=4, column=0, sticky="w", padx=6, pady=4, columnspan=3
        )

        ttk.Label(
            ctrl,
            text=(
                "설명: 드라이런=파일 이동 없이 결과만 확인, "
                "@@@ 제거=파일명 끝 @@@숫자 제거"
            ),
        ).grid(row=5, column=0, columnspan=3, sticky="w", padx=6, pady=4)

        result_frame = ttk.Labelframe(parent, text="결과")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        self.result_view = ResultView(
            result_frame, show_filters=True, hidden_statuses={"SKIP"}
        )

    def _select_folder(self) -> None:
        folder = filedialog.askdirectory(title="원본 폴더 선택")
        if folder:
            self.source_var.set(folder)

    def _run(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        if self.strip_thread and self.strip_thread.is_alive():
            return
        folder = self.source_var.get()
        if not folder:
            messagebox.showwarning("파일명 변경", "원본 폴더를 선택하세요.")
            return
        order = [item.strip() for item in self.order_var.get().split(",") if item.strip()]
        if not order:
            messagebox.showwarning("파일명 변경", "변수 순서를 입력하세요.")
            return

        variables_by_name = {var.name: var for var in self.state.preset.variables}
        missing = [name for name in order if name not in variables_by_name]
        if missing:
            messagebox.showwarning("파일명 변경", f"없는 변수: {', '.join(missing)}")
            return

        template = self.template_var.get().strip()
        if not template:
            template = "_".join(f"[{key}]" for key in order)

        variables_payload = [
            {
                "name": variables_by_name[key].name,
                "values": [
                    {"name": v.name, "tags": v.tags}
                    for v in variables_by_name[key].values
                ],
            }
            for key in order
        ]

        self.stats = {"ok": 0, "unknown": 0, "conflict": 0, "error": 0}
        self.total = 0
        self.processed = 0
        self.start_time = time.monotonic()
        self.issue_path = None
        self.issue_handle = None
        self.issue_count = 0
        if self.result_view:
            self.result_view.clear()
        self.status_var.set("실행 준비 중...")
        self.run_button.config(state="disabled")
        self.strip_button.config(state="disabled")

        self.queue = queue.Queue()
        payload = {
            "folder": folder,
            "order": order,
            "template": template,
            "prefix_mode": bool(self.prefix_var.get()),
            "dry_run": bool(self.dry_run_var.get()),
            "include_negative": bool(self.include_negative_var.get()),
            "progress_step": 200,
            "variables": variables_payload,
        }
        self.thread = threading.Thread(
            target=run_sidecar_job,
            args=("rename", payload, self.queue.put),
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
                        "target": message.get("target"),
                        "message": message.get("message"),
                    }
                    record = self._make_record(status, payload)
                    self.processed += 1
                    if status == "OK":
                        self.stats["ok"] += 1
                    elif status == "UNKNOWN":
                        self.stats["unknown"] += 1
                        self._write_issue(status, record["text"])
                    elif status == "CONFLICT":
                        self.stats["conflict"] += 1
                        self._write_issue(status, record["text"])
                    elif status == "ERROR":
                        self.stats["error"] += 1
                        self._write_issue(status, record["text"])
                    if self.result_view:
                        self.result_view.add_record(record)
                elif msg_type == "progress":
                    processed = int(message.get("processed") or 0)
                    total = int(message.get("total") or 0)
                    self.processed = max(self.processed, processed)
                    if total:
                        self.total = total
                elif msg_type == "done":
                    self.processed = max(self.processed, int(message.get("processed") or 0))
                    self.status_var.set(self._format_status("완료"))
                    self.run_button.config(state="normal")
                    self.strip_button.config(state="normal")
                    self._close_issue_log()
                    logger.info("Rename done: %s", self.stats)
                    return
                elif msg_type == "error":
                    self.run_button.config(state="normal")
                    self.strip_button.config(state="normal")
                    messagebox.showerror("파일명 변경", message.get("message") or "error")
                    return
        except queue.Empty:
            pass

        if updated:
            self.status_var.set(self._format_status("진행"))
        self.app.root.after(100, self._poll_queue)

    def _run_strip(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        if self.strip_thread and self.strip_thread.is_alive():
            return
        folder = self.source_var.get()
        if not folder:
            messagebox.showwarning("@@@ 제거", "원본 폴더를 선택하세요.")
            return

        self.strip_stats = {"ok": 0, "skip": 0, "error": 0}
        self.strip_total = 0
        self.strip_processed = 0
        self.strip_start_time = time.monotonic()
        if self.result_view:
            self.result_view.clear()
        self.status_var.set("@@@ 제거 준비 중...")
        self.run_button.config(state="disabled")
        self.strip_button.config(state="disabled")

        self.strip_queue = queue.Queue()
        payload = {
            "folder": folder,
            "dry_run": bool(self.dry_run_var.get()),
            "progress_step": 200,
        }
        self.strip_thread = threading.Thread(
            target=run_sidecar_job,
            args=("strip_suffix", payload, self.strip_queue.put),
            daemon=True,
        )
        self.strip_thread.start()
        self.app.root.after(100, self._poll_strip_queue)

    def _poll_strip_queue(self) -> None:
        if not self.strip_queue:
            return
        updated = False
        try:
            while True:
                message = self.strip_queue.get_nowait()
                updated = True
                msg_type = message.get("type")
                if msg_type == "result":
                    status = message.get("status") or "OK"
                    payload = {
                        "source": message.get("source"),
                        "target": message.get("target"),
                        "message": message.get("message"),
                    }
                    record = self._make_record(status, payload)
                    self.strip_processed += 1
                    if status == "OK":
                        self.strip_stats["ok"] += 1
                    elif status == "SKIP":
                        self.strip_stats["skip"] += 1
                    elif status == "ERROR":
                        self.strip_stats["error"] += 1
                    if self.result_view:
                        self.result_view.add_record(record)
                elif msg_type == "progress":
                    processed = int(message.get("processed") or 0)
                    total = int(message.get("total") or 0)
                    self.strip_processed = max(self.strip_processed, processed)
                    if total:
                        self.strip_total = total
                elif msg_type == "done":
                    self.strip_processed = max(
                        self.strip_processed, int(message.get("processed") or 0)
                    )
                    self.status_var.set(self._format_strip_status("완료"))
                    self.run_button.config(state="normal")
                    self.strip_button.config(state="normal")
                    logger.info("Strip done: %s", self.strip_stats)
                    return
                elif msg_type == "error":
                    self.run_button.config(state="normal")
                    self.strip_button.config(state="normal")
                    messagebox.showerror("@@@ 제거", message.get("message") or "error")
                    return
        except queue.Empty:
            pass

        if updated:
            self.status_var.set(self._format_strip_status("진행"))
        self.app.root.after(100, self._poll_strip_queue)

    def _format_status(self, prefix: str) -> str:
        eta = format_eta(self.processed, self.total, self.start_time)
        return (
            f"{prefix}: {self.processed}/{self.total} "
            f"OK {self.stats['ok']} UNKNOWN {self.stats['unknown']} "
            f"CONFLICT {self.stats['conflict']} ERROR {self.stats['error']} ETA {eta}"
        )

    def _format_strip_status(self, prefix: str) -> str:
        eta = format_eta(self.strip_processed, self.strip_total, self.strip_start_time)
        return (
            f"{prefix}: {self.strip_processed}/{self.strip_total} "
            f"OK {self.strip_stats['ok']} SKIP {self.strip_stats['skip']} "
            f"ERROR {self.strip_stats['error']} ETA {eta}"
        )

    def _write_issue(self, status: str, text: str) -> None:
        if not self.issue_handle:
            folder = self.source_var.get() or "."
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.issue_path = str(Path(folder) / f"issues_rename_{timestamp}.txt")
            self.issue_handle = open(self.issue_path, "w", encoding="utf-8")
            self.app.set_issue_log("rename", self.issue_path)
        self.issue_handle.write(f"{status} | {text}\n")
        self.issue_handle.flush()
        self.issue_count += 1

    def _close_issue_log(self) -> None:
        if self.issue_handle:
            self.issue_handle.close()
            logger.info("Issues saved: %s (%d)", self.issue_path, self.issue_count)
            self.issue_handle = None
            if self.issue_count > 0 and self.issue_path:
                open_in_default_app(self.issue_path)

    def _make_record(self, status: str, payload: dict) -> dict:
        source = payload.get("source")
        target = payload.get("target")
        message = payload.get("message")
        if status == "OK" and target:
            text = f"OK | {source} -> {target}"
        elif message:
            text = f"{status} | {source} | {message}"
        else:
            text = f"{status} | {source}"
        preview_path = target or source
        return {
            "status": status,
            "text": text,
            "source": source,
            "target": target,
            "preview": preview_path,
        }
