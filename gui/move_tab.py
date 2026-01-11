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


class MoveTab:
    def __init__(self, parent: ttk.Frame, app: "RuleEditorApp") -> None:
        self.app = app
        self.state = app.state

        self.source_var = tk.StringVar()
        self.target_var = tk.StringVar()
        self.variable_var = tk.StringVar()
        self.template_var = tk.StringVar(value="[value]")
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

        self._build(parent)

    def _build(self, parent: ttk.Frame) -> None:
        ctrl = ttk.Labelframe(parent, text="폴더 분류")
        ctrl.pack(fill=tk.X, padx=10, pady=8)
        ctrl.columnconfigure(1, weight=1)

        ttk.Label(ctrl, text="원본 폴더").grid(
            row=0, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Entry(ctrl, textvariable=self.source_var, width=60).grid(
            row=0, column=1, sticky="we", padx=6, pady=6
        )
        ttk.Button(ctrl, text="찾기", command=self._select_source).grid(
            row=0, column=2, padx=6, pady=6
        )

        ttk.Label(ctrl, text="대상 폴더").grid(
            row=1, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Entry(ctrl, textvariable=self.target_var, width=60).grid(
            row=1, column=1, sticky="we", padx=6, pady=6
        )
        ttk.Button(ctrl, text="찾기", command=self._select_target).grid(
            row=1, column=2, padx=6, pady=6
        )

        ttk.Label(ctrl, text="변수").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        self.variable_combo = ttk.Combobox(
            ctrl, textvariable=self.variable_var, state="readonly"
        )
        self.variable_combo.grid(row=2, column=1, sticky="we", padx=6, pady=6)

        ttk.Label(ctrl, text="폴더 템플릿").grid(
            row=3, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Entry(ctrl, textvariable=self.template_var, width=60).grid(
            row=3, column=1, sticky="we", padx=6, pady=6
        )
        ttk.Checkbutton(
            ctrl, text="네거티브 태그 포함", variable=self.include_negative_var
        ).grid(row=3, column=2, padx=6, pady=6)

        options = ttk.Frame(ctrl)
        options.grid(row=4, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        ttk.Checkbutton(options, text="드라이런", variable=self.dry_run_var).pack(
            side=tk.LEFT
        )

        self.run_button = ttk.Button(ctrl, text="실행", command=self._run)
        self.run_button.grid(row=4, column=2, padx=6, pady=4)

        ttk.Label(ctrl, textvariable=self.status_var).grid(
            row=5, column=0, sticky="w", padx=6, pady=4, columnspan=3
        )
        ttk.Label(
            ctrl, text="설명: 드라이런=파일 이동 없이 결과만 확인"
        ).grid(row=6, column=0, columnspan=3, sticky="w", padx=6, pady=4)

        result_frame = ttk.Labelframe(parent, text="결과")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        self.result_view = ResultView(result_frame, show_filters=True)

    def refresh_variable_options(self, keys: list[str]) -> None:
        self.variable_combo["values"] = keys
        if self.variable_var.get() not in keys:
            self.variable_var.set(keys[0] if keys else "")

    def _select_source(self) -> None:
        folder = filedialog.askdirectory(title="원본 폴더 선택")
        if folder:
            self.source_var.set(folder)

    def _select_target(self) -> None:
        folder = filedialog.askdirectory(title="대상 폴더 선택")
        if folder:
            self.target_var.set(folder)

    def _run(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        source = self.source_var.get()
        target = self.target_var.get()
        if not source:
            messagebox.showwarning("폴더 분류", "원본 폴더를 선택하세요.")
            return
        if not target:
            messagebox.showwarning("폴더 분류", "대상 폴더를 선택하세요.")
            return
        key = self.variable_var.get().strip()
        if not key:
            messagebox.showwarning("폴더 분류", "변수를 선택하세요.")
            return

        variables_by_name = {var.name: var for var in self.state.preset.variables}
        if key not in variables_by_name:
            messagebox.showwarning("폴더 분류", "없는 변수입니다.")
            return

        template = self.template_var.get().strip() or "[value]"

        variables_payload = [
            {
                "name": variables_by_name[key].name,
                "values": [
                    {"name": v.name, "tags": v.tags}
                    for v in variables_by_name[key].values
                ],
            },
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
        self.status_var.set("진행 준비 중...")
        self.run_button.config(state="disabled")

        self.queue = queue.Queue()
        payload = {
            "folder": source,
            "variable_name": key,
            "template": template,
            "target_root": target,
            "dry_run": bool(self.dry_run_var.get()),
            "include_negative": bool(self.include_negative_var.get()),
            "progress_step": 200,
            "variables": variables_payload,
        }
        self.thread = threading.Thread(
            target=run_sidecar_job,
            args=("move", payload, self.queue.put),
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
                    self._close_issue_log()
                    logger.info("Move done: %s", self.stats)
                    return
                elif msg_type == "error":
                    self.run_button.config(state="normal")
                    messagebox.showerror("폴더 분류", message.get("message") or "error")
                    return
        except queue.Empty:
            pass

        if updated:
            self.status_var.set(self._format_status("진행"))
        self.app.root.after(100, self._poll_queue)

    def _format_status(self, prefix: str) -> str:
        eta = format_eta(self.processed, self.total, self.start_time)
        return (
            f"{prefix}: {self.processed}/{self.total} "
            f"OK {self.stats['ok']} UNKNOWN {self.stats['unknown']} "
            f"CONFLICT {self.stats['conflict']} ERROR {self.stats['error']} ETA {eta}"
        )

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

    def _write_issue(self, status: str, text: str) -> None:
        if not self.issue_handle:
            folder = self.source_var.get() or "."
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.issue_path = str(Path(folder) / f"issues_move_{timestamp}.txt")
            self.issue_handle = open(self.issue_path, "w", encoding="utf-8")
            self.app.set_issue_log("move", self.issue_path)
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
