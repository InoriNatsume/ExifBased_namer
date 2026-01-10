import logging
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.normalize_novelai import split_novelai_tags
from core.progress import format_eta
from gui.common import iter_image_files
from gui.result_view import ResultView
from gui.tasks import search_task


logger = logging.getLogger(__name__)


class SearchTab:
    def __init__(self, parent: ttk.Frame, app: "RuleEditorApp") -> None:
        self.app = app
        self.folder_var = tk.StringVar()
        self.tags_var = tk.StringVar()
        self.include_negative_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="대기")

        self.queue: queue.Queue | None = None
        self.thread: threading.Thread | None = None
        self.stats = {"ok": 0, "error": 0}
        self.total = 0
        self.processed = 0
        self.start_time = 0.0
        self.result_view: ResultView | None = None

        self._build(parent)

    def _build(self, parent: ttk.Frame) -> None:
        ctrl = ttk.Labelframe(parent, text="검색")
        ctrl.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(ctrl, text="폴더").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(ctrl, textvariable=self.folder_var, width=60).grid(
            row=0, column=1, sticky="we", padx=6, pady=6
        )
        ttk.Button(ctrl, text="찾기", command=self._select_folder).grid(
            row=0, column=2, padx=6, pady=6
        )

        ttk.Label(ctrl, text="필수 태그").grid(
            row=1, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Entry(ctrl, textvariable=self.tags_var, width=60).grid(
            row=1, column=1, sticky="we", padx=6, pady=6
        )
        ttk.Checkbutton(
            ctrl, text="네거티브 태그 포함", variable=self.include_negative_var
        ).grid(row=1, column=2, padx=6, pady=6)

        self.run_button = ttk.Button(ctrl, text="검색", command=self._run_search)
        self.run_button.grid(
            row=2, column=1, sticky="w", padx=6, pady=6
        )
        ttk.Label(ctrl, textvariable=self.status_var).grid(
            row=2, column=2, sticky="w", padx=6, pady=6
        )

        ttk.Label(
            ctrl,
            text="설명: 필수 태그는 쉼표로 입력하고 AND 조건으로만 검사합니다.",
        ).grid(row=3, column=0, columnspan=3, sticky="w", padx=6, pady=4)

        result_frame = ttk.Labelframe(parent, text="일치 파일")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        self.result_view = ResultView(result_frame, show_filters=False)

    def _select_folder(self) -> None:
        folder = filedialog.askdirectory(title="폴더 선택")
        if folder:
            self.folder_var.set(folder)

    def _run_search(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        folder = self.folder_var.get()
        if not folder:
            messagebox.showwarning("검색", "먼저 폴더를 선택하세요.")
            return
        required_tags = split_novelai_tags(self.tags_var.get())
        if not required_tags:
            messagebox.showwarning("검색", "필수 태그를 입력하세요.")
            return

        include_negative = bool(self.include_negative_var.get())
        image_paths = iter_image_files(folder)
        if not image_paths:
            messagebox.showinfo("검색", "이미지가 없습니다.")
            return

        self.stats = {"ok": 0, "error": 0}
        self.total = len(image_paths)
        self.processed = 0
        self.start_time = time.monotonic()
        if self.result_view:
            self.result_view.clear()
        self.status_var.set("검색 중...")
        self.run_button.config(state="disabled")

        self.queue = queue.Queue()
        args = (
            self.queue,
            image_paths,
            required_tags,
            include_negative,
        )
        self.thread = threading.Thread(target=search_task, args=args, daemon=True)
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
                    if self.result_view:
                        self.result_view.add_record(record)
                elif message[0] == "progress":
                    _, processed, total, matches, errors = message
                    self.processed = processed
                    self.total = total
                    self.stats["ok"] = matches
                    self.stats["error"] = errors
                elif message[0] == "done":
                    matches, errors = message[1], message[2]
                    self.stats["ok"] = matches
                    self.stats["error"] = errors
                    self.processed = self.total
                    self.status_var.set(self._format_status("완료"))
                    self.run_button.config(state="normal")
                    logger.info("Search done: %d/%d matched", matches, self.total)
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
            f"일치 {self.stats['ok']} 오류 {self.stats['error']} ETA {eta}"
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
