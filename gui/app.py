import logging
import multiprocessing
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from gui.editor_tab import EditorTab
from gui.log_tab import GuiLogHandler, LogTab
from gui.move_tab import MoveTab
from gui.rename_tab import RenameTab
from gui.search_tab import SearchTab
from gui.state import AppState


class RuleEditorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.state = AppState()
        self.root.title("NAI 태그 분류기")
        self.root.geometry("1200x760")

        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        nav_frame = ttk.Frame(container)
        nav_frame.grid(row=0, column=0, sticky="ns")
        nav_frame.configure(width=200)
        nav_frame.grid_propagate(False)

        content_frame = ttk.Frame(container)
        content_frame.grid(row=0, column=1, sticky="nsew")
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(0, weight=1)

        ttk.Label(nav_frame, text="NAI 태그 분류기", font=("맑은 고딕", 14, "bold")).pack(
            anchor="w", padx=12, pady=(16, 4)
        )
        ttk.Label(nav_frame, text="Tkinter 프로토타입").pack(
            anchor="w", padx=12, pady=(0, 16)
        )

        self.nav_buttons: dict[str, ttk.Button] = {}
        self.frames: dict[str, ttk.Frame] = {}

        self.frames["editor"] = ttk.Frame(content_frame)
        self.frames["search"] = ttk.Frame(content_frame)
        self.frames["rename"] = ttk.Frame(content_frame)
        self.frames["move"] = ttk.Frame(content_frame)
        self.frames["log"] = ttk.Frame(content_frame)

        self.editor = EditorTab(self.frames["editor"], self)
        self.search = SearchTab(self.frames["search"], self)
        self.rename = RenameTab(self.frames["rename"], self)
        self.move = MoveTab(self.frames["move"], self)
        self.log_tab = LogTab(self.frames["log"], self)
        self.on_preset_changed()

        self._add_nav_button(nav_frame, "editor", "편집")
        self._add_nav_button(nav_frame, "search", "검색")
        self._add_nav_button(nav_frame, "rename", "파일명 변경")
        self._add_nav_button(nav_frame, "move", "폴더 분류")
        self._add_nav_button(nav_frame, "log", "로그")

        self.show_frame("editor")
        self._setup_logging()

    def _add_nav_button(self, parent: ttk.Frame, key: str, label: str) -> None:
        btn = ttk.Button(parent, text=label, command=lambda: self.show_frame(key))
        btn.pack(fill=tk.X, padx=10, pady=4)
        self.nav_buttons[key] = btn

    def show_frame(self, key: str) -> None:
        for name, frame in self.frames.items():
            frame.grid_forget()
            if name in self.nav_buttons:
                self.nav_buttons[name].state(["!pressed"])
        frame = self.frames.get(key)
        if frame is None:
            return
        frame.grid(row=0, column=0, sticky="nsew")
        if key in self.nav_buttons:
            self.nav_buttons[key].state(["pressed"])

    def on_preset_changed(self) -> None:
        names = [var.name for var in self.state.preset.variables]
        self.move.refresh_variable_options(names)

    def _setup_logging(self) -> None:
        root_logger = logging.getLogger()
        if any(isinstance(handler, GuiLogHandler) for handler in root_logger.handlers):
            return
        handler = GuiLogHandler(self.log_tab.append)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root_logger.addHandler(handler)

    def set_issue_log(self, kind: str, path: str) -> None:
        if self.log_tab:
            self.log_tab.set_issue_path(kind, path)


def main() -> None:
    multiprocessing.freeze_support()
    logging.basicConfig(level=logging.INFO)
    root = tk.Tk()
    RuleEditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
