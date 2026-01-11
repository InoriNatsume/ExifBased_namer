import logging
import tkinter as tk
from tkinter import ttk

from gui.common import open_in_default_app


class GuiLogHandler(logging.Handler):
    def __init__(self, emit_callback) -> None:
        super().__init__()
        self.emit_callback = emit_callback

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:
            message = record.getMessage()
        self.emit_callback(message)


class LogTab:
    def __init__(self, parent: ttk.Frame, app: "RuleEditorApp") -> None:
        self.app = app
        self.root = app.root
        self.text: tk.Text | None = None
        self.issue_paths: dict[str, tk.StringVar] = {
            "rename": tk.StringVar(),
            "move": tk.StringVar(),
        }

        self._build(parent)

    def _build(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(header, text="최근 로그").pack(side=tk.LEFT)
        ttk.Button(header, text="복사", command=self._copy_logs).pack(
            side=tk.RIGHT, padx=4
        )
        ttk.Button(header, text="지우기", command=self._clear_logs).pack(side=tk.RIGHT)

        body = ttk.Frame(parent)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.text = tk.Text(body, height=12, wrap="word")
        scrollbar = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        issue_frame = ttk.Labelframe(parent, text="문제 로그")
        issue_frame.pack(fill=tk.X, padx=10, pady=8)
        issue_frame.columnconfigure(1, weight=1)

        ttk.Label(issue_frame, text="파일명 변경").grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )
        ttk.Entry(
            issue_frame, textvariable=self.issue_paths["rename"], state="readonly"
        ).grid(row=0, column=1, sticky="we", padx=6, pady=4)
        ttk.Button(
            issue_frame, text="열기", command=lambda: self._open_issue("rename")
        ).grid(row=0, column=2, padx=6, pady=4)

        ttk.Label(issue_frame, text="폴더 분류").grid(
            row=1, column=0, sticky="w", padx=6, pady=4
        )
        ttk.Entry(
            issue_frame, textvariable=self.issue_paths["move"], state="readonly"
        ).grid(row=1, column=1, sticky="we", padx=6, pady=4)
        ttk.Button(
            issue_frame, text="열기", command=lambda: self._open_issue("move")
        ).grid(row=1, column=2, padx=6, pady=4)

    def append(self, message: str) -> None:
        if not self.text:
            return

        def _append() -> None:
            if not self.text:
                return
            self.text.insert(tk.END, f"{message}\n")
            self.text.see(tk.END)

        self.root.after(0, _append)

    def set_issue_path(self, kind: str, path: str) -> None:
        if kind in self.issue_paths:
            self.issue_paths[kind].set(path)

    def _open_issue(self, kind: str) -> None:
        path = self.issue_paths.get(kind)
        if not path:
            return
        open_in_default_app(path.get())

    def _clear_logs(self) -> None:
        if not self.text:
            return
        self.text.delete("1.0", tk.END)

    def _copy_logs(self) -> None:
        if not self.text:
            return
        content = self.text.get("1.0", tk.END).strip()
        if not content:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
