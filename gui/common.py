import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk


LIST_LIMIT = 2000


def iter_image_files(folder: str) -> list[str]:
    results: list[str] = []
    for root, _dirs, files in os.walk(folder):
        for name in files:
            lower = name.lower()
            if lower.endswith((".png", ".webp", ".jpg", ".jpeg")):
                results.append(str(Path(root) / name))
    return results


def simple_input(root: tk.Tk, title: str, prompt: str) -> str | None:
    dialog = tk.Toplevel(root)
    dialog.title(title)
    dialog.transient(root)
    dialog.grab_set()

    ttk.Label(dialog, text=prompt).pack(padx=10, pady=8)
    value_var = tk.StringVar()
    entry = ttk.Entry(dialog, textvariable=value_var, width=40)
    entry.pack(padx=10, pady=6)
    entry.focus_set()

    result: dict[str, str | None] = {"value": None}

    def submit() -> None:
        result["value"] = value_var.get().strip() or None
        dialog.destroy()

    ttk.Button(dialog, text="확인", command=submit).pack(pady=8)
    dialog.wait_window()
    return result["value"]


def open_in_default_app(path: str) -> None:
    if not path:
        return
    if not os.path.exists(path):
        return
    os.startfile(path)
