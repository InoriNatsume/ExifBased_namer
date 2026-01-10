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
from gui.move_tab import MoveTab
from gui.rename_tab import RenameTab
from gui.search_tab import SearchTab
from gui.state import AppState


class RuleEditorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.state = AppState()
        self.root.title("NAI 태그 분류기")
        self.root.geometry("1100x720")

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True)

        editor_tab = ttk.Frame(notebook)
        search_tab = ttk.Frame(notebook)
        rename_tab = ttk.Frame(notebook)
        move_tab = ttk.Frame(notebook)

        notebook.add(editor_tab, text="편집")
        notebook.add(search_tab, text="검색")
        notebook.add(rename_tab, text="파일명 변경")
        notebook.add(move_tab, text="폴더 분류")

        self.editor = EditorTab(editor_tab, self)
        self.search = SearchTab(search_tab, self)
        self.rename = RenameTab(rename_tab, self)
        self.move = MoveTab(move_tab, self)
        self.on_preset_changed()

    def on_preset_changed(self) -> None:
        names = [var.name for var in self.state.preset.variables]
        self.move.refresh_variable_options(names)


def main() -> None:
    multiprocessing.freeze_support()
    logging.basicConfig(level=logging.INFO)
    root = tk.Tk()
    RuleEditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
