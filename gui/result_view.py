from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from gui.common import LIST_LIMIT


class ResultView:
    def __init__(
        self,
        parent: ttk.Frame,
        *,
        show_filters: bool = True,
        hidden_statuses: set[str] | None = None,
    ) -> None:
        self.show_filters = show_filters
        self.hidden_statuses = set(hidden_statuses or [])
        self.filter_vars: dict[str, tk.BooleanVar] = {}

        self.records: list[dict] = []
        self.filtered_indices: list[int] = []
        self.preview_image = None
        self.preview_path: str | None = None
        self.preview_path_var = tk.StringVar()

        if show_filters:
            filter_frame = ttk.Frame(parent)
            filter_frame.pack(fill=tk.X, padx=6, pady=4)
            for status in ("OK", "UNKNOWN", "CONFLICT", "ERROR"):
                var = tk.BooleanVar(value=True)
                self.filter_vars[status] = var
                ttk.Checkbutton(filter_frame, text=status, variable=var).pack(
                    side=tk.LEFT, padx=6
                )
            ttk.Button(filter_frame, text="필터 적용", command=self.apply_filters).pack(
                side=tk.RIGHT
            )

        pane = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        list_frame = ttk.Frame(pane)
        self.listbox = tk.Listbox(list_frame)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        pane.add(list_frame, weight=2)

        preview_frame = ttk.Frame(pane)
        ttk.Label(preview_frame, textvariable=self.preview_path_var).pack(
            fill=tk.X, padx=6, pady=4
        )
        self.preview_label = tk.Label(preview_frame, text="미리보기 없음", anchor="center")
        self.preview_label.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.preview_label.bind("<Configure>", self._on_preview_resize)
        pane.add(preview_frame, weight=1)

    def clear(self) -> None:
        self.records = []
        self.filtered_indices = []
        self.listbox.delete(0, tk.END)
        self.preview_path = None
        self.preview_path_var.set("")
        self.preview_label.config(text="미리보기 없음", image="")
        self.preview_image = None

    def add_record(self, record: dict) -> None:
        self.records.append(record)
        if self._is_visible(record.get("status")) and self.listbox.size() < LIST_LIMIT:
            self.filtered_indices.append(len(self.records) - 1)
            self.listbox.insert(tk.END, record.get("text", ""))

    def apply_filters(self) -> None:
        self.listbox.delete(0, tk.END)
        self.filtered_indices = []
        for idx, record in enumerate(self.records):
            if not self._is_visible(record.get("status")):
                continue
            if self.listbox.size() >= LIST_LIMIT:
                break
            self.filtered_indices.append(idx)
            self.listbox.insert(tk.END, record.get("text", ""))

    def _is_visible(self, status: str | None) -> bool:
        if status in self.hidden_statuses:
            return False
        if not self.show_filters:
            return True
        if status in self.filter_vars:
            return bool(self.filter_vars[status].get())
        return True

    def _on_select(self, _event: tk.Event) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        list_index = selection[0]
        if list_index >= len(self.filtered_indices):
            return
        record = self.records[self.filtered_indices[list_index]]
        path = record.get("preview")
        self.preview_path = path
        self.preview_path_var.set(path or "")
        self._render_preview()

    def _on_preview_resize(self, _event: tk.Event) -> None:
        self._render_preview()

    def _render_preview(self) -> None:
        path = self.preview_path
        if not path or not Path(path).exists():
            self.preview_label.config(text="미리보기 없음", image="")
            self.preview_image = None
            return
        try:
            with Image.open(path) as opened:
                img = opened.copy()
        except Exception:
            self.preview_label.config(text="미리보기 실패", image="")
            self.preview_image = None
            return
        width = self.preview_label.winfo_width() or 200
        height = self.preview_label.winfo_height() or 200
        img.thumbnail((width - 10, height - 10))
        self.preview_image = ImageTk.PhotoImage(img)
        self.preview_label.config(image=self.preview_image, text="")
