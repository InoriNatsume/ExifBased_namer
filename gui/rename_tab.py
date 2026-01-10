from datetime import datetime
import logging
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.progress import format_eta
from core.worker import build_variable_specs
from gui.common import iter_image_files, open_in_default_app
from gui.result_view import ResultView
from gui.tasks import rename_task, strip_suffix_task


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
        self.issue_path_var = tk.StringVar()

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

        ttk.Label(ctrl, text="원본 폴더").grid(
            row=0, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Entry(ctrl, textvariable=self.source_var, width=60).grid(
            row=0, column=1, sticky="we", padx=6, pady=6
        )
        ttk.Button(ctrl, text="찾기", command=self._select_folder).grid(
            row=0, column=2, padx=6, pady=6
        )

        ttk.Label(ctrl, text="변수 이름 순서").grid(
            row=1, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Entry(ctrl, textvariable=self.order_var, width=60).grid(
            row=1, column=1, sticky="we", padx=6, pady=6
        )
        ttk.Checkbutton(ctrl, text="접두사 모드", variable=self.prefix_var).grid(
            row=1, column=2, padx=6, pady=6
        )

        ttk.Label(ctrl, text="템플릿").grid(
            row=2, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Entry(ctrl, textvariable=self.template_var, width=60).grid(
            row=2, column=1, sticky="we", padx=6, pady=6
        )
        ttk.Checkbutton(
            ctrl, text="네거티브 태그 포함", variable=self.include_negative_var
        ).grid(row=2, column=2, padx=6, pady=6)

        ttk.Checkbutton(ctrl, text="드라이런", variable=self.dry_run_var).grid(
            row=3, column=1, sticky="w", padx=6, pady=6
        )
        self.run_button = ttk.Button(ctrl, text="실행", command=self._run)
        self.run_button.grid(row=3, column=2, padx=6, pady=6)
        self.strip_button = ttk.Button(
            ctrl, text="@@@ 제거", command=self._run_strip
        )
        self.strip_button.grid(row=3, column=0, padx=6, pady=6)
        ttk.Label(ctrl, textvariable=self.status_var).grid(
            row=4, column=0, sticky="w", padx=6, pady=6, columnspan=3
        )
        ttk.Label(ctrl, text="문제 로그").grid(
            row=5, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Entry(ctrl, textvariable=self.issue_path_var, width=60, state="readonly").grid(
            row=5, column=1, sticky="we", padx=6, pady=6
        )
        ttk.Button(ctrl, text="열기", command=self._open_issue_log).grid(
            row=5, column=2, padx=6, pady=6
        )
        ttk.Label(
            ctrl,
            text="설명: 드라이런=파일 변경 없이 결과만 확인, @@@ 제거=파일명 끝의 @@@숫자를 삭제",
        ).grid(row=6, column=0, columnspan=3, sticky="w", padx=6, pady=4)

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
            messagebox.showwarning("파일명 변경", "먼저 원본 폴더를 선택하세요.")
            return
        order = [item.strip() for item in self.order_var.get().split(",") if item.strip()]
        if not order:
            messagebox.showwarning("파일명 변경", "변수 순서를 입력하세요.")
            return

        variables_by_name = {var.name: var for var in self.state.preset.variables}
        missing = [name for name in order if name not in variables_by_name]
        if missing:
            messagebox.showwarning("파일명 변경", f"알 수 없는 변수 이름: {', '.join(missing)}")
            return

        template = self.template_var.get().strip()
        if not template:
            template = "_".join(f"[{key}]" for key in order)

        image_paths = iter_image_files(folder)
        if not image_paths:
            messagebox.showinfo("파일명 변경", "이미지가 없습니다.")
            return

        vars_data = []
        for key in order:
            var = variables_by_name[key]
            vars_data.append(
                {"name": var.name, "values": [{"name": v.name, "tags": v.tags} for v in var.values]}
            )
        specs = build_variable_specs(vars_data)

        self.stats = {"ok": 0, "unknown": 0, "conflict": 0, "error": 0}
        self.total = len(image_paths)
        self.processed = 0
        self.start_time = time.monotonic()
        self.issue_path = None
        self.issue_handle = None
        self.issue_count = 0
        if self.result_view:
            self.result_view.clear()
        self.status_var.set("진행 중...")
        self.run_button.config(state="disabled")
        self.strip_button.config(state="disabled")
        self.issue_path_var.set("")

        self.queue = queue.Queue()
        args = (
            self.queue,
            image_paths,
            specs,
            order,
            template,
            bool(self.prefix_var.get()),
            bool(self.dry_run_var.get()),
            bool(self.include_negative_var.get()),
        )
        self.thread = threading.Thread(target=rename_task, args=args, daemon=True)
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
                if message[0] == "result":
                    status, payload = message[1], message[2]
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
                elif message[0] == "done":
                    self.status_var.set(self._format_status("완료"))
                    self.run_button.config(state="normal")
                    self.strip_button.config(state="normal")
                    self._close_issue_log()
                    logger.info("Rename done: %s", self.stats)
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
            messagebox.showwarning("@@@ 제거", "먼저 원본 폴더를 선택하세요.")
            return

        image_paths = iter_image_files(folder)
        if not image_paths:
            messagebox.showinfo("@@@ 제거", "이미지가 없습니다.")
            return

        self.strip_stats = {"ok": 0, "skip": 0, "error": 0}
        self.strip_total = len(image_paths)
        self.strip_processed = 0
        self.strip_start_time = time.monotonic()
        if self.result_view:
            self.result_view.clear()
        self.status_var.set("@@@ 제거 중...")
        self.run_button.config(state="disabled")
        self.strip_button.config(state="disabled")
        self.issue_path_var.set("")

        self.strip_queue = queue.Queue()
        args = (
            self.strip_queue,
            image_paths,
            bool(self.dry_run_var.get()),
        )
        self.strip_thread = threading.Thread(target=strip_suffix_task, args=args, daemon=True)
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
                if message[0] == "result":
                    status, payload = message[1], message[2]
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
                elif message[0] == "done":
                    self.status_var.set(self._format_strip_status("완료"))
                    self.run_button.config(state="normal")
                    self.strip_button.config(state="normal")
                    logger.info("Strip done: %s", self.strip_stats)
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
            self.issue_path_var.set(self.issue_path)
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

    def _open_issue_log(self) -> None:
        if self.issue_path:
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
        return {"status": status, "text": text, "source": source, "target": target, "preview": preview_path}
