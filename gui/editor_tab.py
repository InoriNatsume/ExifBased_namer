import json
import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.adapters.legacy import import_legacy_payload
from core.adapters.nais import export_variable_to_nais, import_nais_payload
from core.normalize_novelai import split_novelai_tags
from core.preset_io import load_preset, save_preset
from core.schema import Variable, VariableValue
from core.tag_sets import remove_common_tags_from_values
from core.value_conflicts import detect_value_conflicts, filter_value_conflicts
from gui.common import simple_input


logger = logging.getLogger(__name__)


class EditorTab:
    def __init__(self, parent: ttk.Frame, app: "RuleEditorApp") -> None:
        self.app = app
        self.state = app.state

        self.selected_variable_index: int | None = None
        self.selected_value_index: int | None = None

        self.preset_name_var = tk.StringVar()
        self.variable_name_var = tk.StringVar()
        self.value_name_var = tk.StringVar()
        self.value_tags_var = tk.StringVar()
        self.bulk_prefix_var = tk.StringVar()
        self.bulk_suffix_var = tk.StringVar()
        self.bulk_find_var = tk.StringVar()
        self.bulk_replace_var = tk.StringVar()
        self.bulk_remove_var = tk.StringVar()
        self.common_tags_by_var: dict[str, list[str]] = {}

        self._build(parent)

    def _build(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(header, text="프리셋 이름").pack(side=tk.LEFT)
        ttk.Entry(header, textvariable=self.preset_name_var, width=30).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(header, text="이름 적용", command=self._apply_preset_name).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(header, text="프리셋 불러오기", command=self._load_preset).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(header, text="프리셋 저장", command=self._save_preset).pack(
            side=tk.LEFT
        )

        ttk.Label(
            parent,
            text="설명: 변수=분류 기준, 값=변수 안의 항목, 태그 조합=값이 필요로 하는 태그 묶음",
        ).pack(anchor="w", padx=10, pady=4)

        main = ttk.Frame(parent)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.columnconfigure(2, weight=1)
        main.rowconfigure(0, weight=1)

        var_frame = ttk.Labelframe(main, text="변수")
        var_frame.grid(row=0, column=0, sticky="nsew", padx=6)
        self.variables_list = tk.Listbox(var_frame, height=18)
        self.variables_list.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.variables_list.bind("<<ListboxSelect>>", self._on_variable_select)

        var_btns = ttk.Frame(var_frame)
        var_btns.pack(fill=tk.X, padx=6, pady=4)
        ttk.Button(var_btns, text="추가", command=self._add_variable).pack(side=tk.LEFT)
        ttk.Button(var_btns, text="삭제", command=self._delete_variable).pack(
            side=tk.LEFT, padx=4
        )

        val_frame = ttk.Labelframe(main, text="값")
        val_frame.grid(row=0, column=1, sticky="nsew", padx=6)
        self.values_list = tk.Listbox(val_frame, height=18)
        self.values_list.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.values_list.bind("<<ListboxSelect>>", self._on_value_select)

        val_btns = ttk.Frame(val_frame)
        val_btns.pack(fill=tk.X, padx=6, pady=4)
        ttk.Button(val_btns, text="추가", command=self._add_value).pack(side=tk.LEFT)
        ttk.Button(val_btns, text="삭제", command=self._delete_value).pack(
            side=tk.LEFT, padx=4
        )

        io_btns = ttk.Frame(val_frame)
        io_btns.pack(fill=tk.X, padx=6, pady=4)
        ttk.Button(io_btns, text="JSON 불러오기", command=self._import_values).pack(
            side=tk.LEFT
        )
        ttk.Button(io_btns, text="NAIS 내보내기", command=self._export_values).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(io_btns, text="공통 태그 제외", command=self._remove_common_tags).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(io_btns, text="공통 태그 보기", command=self._show_common_tags).pack(
            side=tk.LEFT, padx=4
        )

        detail_frame = ttk.Labelframe(main, text="상세")
        detail_frame.grid(row=0, column=2, sticky="nsew", padx=6)

        ttk.Label(detail_frame, text="변수 이름").pack(anchor="w", padx=6, pady=2)
        ttk.Entry(detail_frame, textvariable=self.variable_name_var).pack(
            fill=tk.X, padx=6
        )
        ttk.Button(detail_frame, text="변수 적용", command=self._apply_variable).pack(
            anchor="w", padx=6, pady=6
        )

        ttk.Separator(detail_frame).pack(fill=tk.X, padx=6, pady=6)

        ttk.Label(detail_frame, text="값 이름").pack(anchor="w", padx=6, pady=2)
        ttk.Entry(detail_frame, textvariable=self.value_name_var).pack(
            fill=tk.X, padx=6
        )
        ttk.Label(detail_frame, text="값 태그").pack(anchor="w", padx=6, pady=2)
        ttk.Entry(detail_frame, textvariable=self.value_tags_var).pack(
            fill=tk.X, padx=6
        )
        ttk.Button(detail_frame, text="값 적용", command=self._apply_value).pack(
            anchor="w", padx=6, pady=6
        )

        bulk_frame = ttk.Labelframe(detail_frame, text="값 이름 일괄 변경")
        bulk_frame.pack(fill=tk.X, padx=6, pady=6)

        ttk.Label(bulk_frame, text="앞에 추가").pack(anchor="w")
        ttk.Entry(bulk_frame, textvariable=self.bulk_prefix_var).pack(fill=tk.X, pady=2)
        ttk.Button(bulk_frame, text="적용", command=self._bulk_add_prefix).pack(
            anchor="w", pady=2
        )

        ttk.Label(bulk_frame, text="뒤에 추가").pack(anchor="w", pady=(6, 0))
        ttk.Entry(bulk_frame, textvariable=self.bulk_suffix_var).pack(fill=tk.X, pady=2)
        ttk.Button(bulk_frame, text="적용", command=self._bulk_add_suffix).pack(
            anchor="w", pady=2
        )

        ttk.Label(bulk_frame, text="단어 바꾸기").pack(anchor="w", pady=(6, 0))
        ttk.Entry(bulk_frame, textvariable=self.bulk_find_var).pack(fill=tk.X, pady=2)
        ttk.Entry(bulk_frame, textvariable=self.bulk_replace_var).pack(
            fill=tk.X, pady=2
        )
        ttk.Button(bulk_frame, text="적용", command=self._bulk_replace).pack(
            anchor="w", pady=2
        )

        ttk.Label(bulk_frame, text="단어 삭제").pack(anchor="w", pady=(6, 0))
        ttk.Entry(bulk_frame, textvariable=self.bulk_remove_var).pack(fill=tk.X, pady=2)
        ttk.Button(bulk_frame, text="적용", command=self._bulk_remove).pack(
            anchor="w", pady=2
        )

    def refresh(self) -> None:
        self.preset_name_var.set(self.state.preset.name or "")
        self._refresh_variables()
        self._refresh_values()

    def _apply_preset_name(self) -> None:
        name = self.preset_name_var.get().strip() or None
        ok, error = self.state.replace_preset(
            self.state.preset.variables,
            name,
        )
        if not ok:
            messagebox.showerror("검증", error)
            return
        logger.info("Preset name updated: %s", name)

    def _load_preset(self) -> None:
        path = filedialog.askopenfilename(
            title="프리셋 불러오기",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            preset = load_preset(path)
        except Exception as exc:
            messagebox.showerror("프리셋 불러오기", f"불러오기 실패: {exc}")
            return
        self.state.load_preset(preset)
        self.selected_variable_index = None
        self.selected_value_index = None
        self.refresh()
        self._load_value_details(None)
        self.app.on_preset_changed()
        logger.info("Preset loaded: %s", path)

    def _save_preset(self) -> None:
        name = self.preset_name_var.get().strip() or None
        ok, error = self.state.replace_preset(
            self.state.preset.variables,
            name,
        )
        if not ok:
            messagebox.showerror("검증", error)
            return
        preset = self.state.preset
        filename = f"{preset.name or 'preset'}.json"
        path = filedialog.asksaveasfilename(
            title="프리셋 저장",
            defaultextension=".json",
            initialfile=filename,
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            save_preset(path, preset)
        except Exception as exc:
            messagebox.showerror("프리셋 저장", f"저장 실패: {exc}")
            return
        logger.info("Preset saved: %s", path)

    def _add_variable(self) -> None:
        name = simple_input(self.app.root, "변수 이름", "변수 이름을 입력하세요")
        if not name:
            return
        new_var = Variable(name=name, values=[])
        variables = list(self.state.preset.variables) + [new_var]
        ok, error = self.state.replace_preset(variables, self.state.preset.name)
        if not ok:
            messagebox.showerror("검증", error)
            return
        self.selected_variable_index = len(variables) - 1
        self._refresh_variables()
        self._refresh_values()
        self.app.on_preset_changed()
        logger.info("Variable added: %s", name)

    def _delete_variable(self) -> None:
        idx = self.selected_variable_index
        if idx is None:
            return
        variables = list(self.state.preset.variables)
        removed = variables[idx].name
        variables.pop(idx)
        ok, error = self.state.replace_preset(variables, self.state.preset.name)
        if not ok:
            messagebox.showerror("검증", error)
            return
        self.selected_variable_index = None
        self.selected_value_index = None
        self._refresh_variables()
        self._refresh_values()
        self._load_value_details(None)
        self.app.on_preset_changed()
        logger.info("Variable deleted: %s", removed)

    def _apply_variable(self) -> None:
        idx = self.selected_variable_index
        if idx is None:
            return
        name = self.variable_name_var.get()
        values = self.state.preset.variables[idx].values
        updated = Variable(name=name, values=values)
        variables = list(self.state.preset.variables)
        variables[idx] = updated
        ok, error = self.state.replace_preset(variables, self.state.preset.name)
        if not ok:
            messagebox.showerror("검증", error)
            return
        self._refresh_variables()
        self.app.on_preset_changed()
        logger.info("Variable updated: %s", name)

    def _add_value(self) -> None:
        var = self._get_selected_variable()
        if var is None:
            return
        name = simple_input(self.app.root, "값 이름", "값 이름을 입력하세요")
        if not name:
            return
        tags_input = simple_input(
            self.app.root,
            "값 태그",
            "태그를 입력하세요 (쉼표로 구분)",
        )
        if not tags_input:
            messagebox.showwarning("값", "태그는 필수입니다.")
            return
        tags = split_novelai_tags(tags_input)
        if not tags:
            messagebox.showwarning("값", "태그는 필수입니다.")
            return
        values = list(var.values) + [VariableValue(name=name, tags=tags)]
        updated = Variable(name=var.name, values=values)
        self._replace_variable(updated)
        self.selected_value_index = len(values) - 1
        self._refresh_values()
        logger.info("Value added: %s -> %s", var.name, name)

    def _delete_value(self) -> None:
        var = self._get_selected_variable()
        idx = self.selected_value_index
        if var is None or idx is None:
            return
        values = list(var.values)
        removed = values[idx].name
        values.pop(idx)
        updated = Variable(name=var.name, values=values)
        self._replace_variable(updated)
        self.selected_value_index = None
        self._refresh_values()
        self._load_value_details(None)
        logger.info("Value deleted: %s -> %s", var.name, removed)

    def _apply_value(self) -> None:
        var = self._get_selected_variable()
        idx = self.selected_value_index
        if var is None or idx is None:
            return
        name = self.value_name_var.get().strip()
        raw_tags = self.value_tags_var.get()
        tags = split_novelai_tags(raw_tags)
        if not tags:
            messagebox.showwarning("값", "태그는 필수입니다.")
            return
        values = list(var.values)
        values[idx] = VariableValue(name=name, tags=tags)
        updated = Variable(name=var.name, values=values)
        self._replace_variable(updated)
        self._refresh_values()
        logger.info("Value updated: %s -> %s", var.name, name)

    def _import_values(self) -> None:
        var = self._get_selected_variable()
        if var is None:
            messagebox.showwarning("불러오기", "먼저 변수를 선택하세요.")
            return
        path = filedialog.askopenfilename(
            title="JSON 불러오기",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception as exc:
            messagebox.showerror("불러오기", f"JSON 로드 실패: {exc}")
            return

        try:
            if isinstance(payload, dict) and isinstance(payload.get("scenes"), list):
                _, values = import_nais_payload(payload)
            else:
                _, values = import_legacy_payload(payload)
        except Exception as exc:
            messagebox.showerror("불러오기", f"지원하지 않는 JSON 형식: {exc}")
            return
        filtered = [value for value in values if value.tags]
        if len(filtered) != len(values):
            messagebox.showwarning("불러오기", "태그가 비어있는 값은 제외되었습니다.")
        if not filtered:
            messagebox.showerror("불러오기", "유효한 값이 없습니다. (태그 비어있음)")
            return

        replace = messagebox.askyesno(
            "불러오기",
            "기존 값을 덮어쓸까요?\n예=덮어쓰기, 아니오=추가",
        )
        merged = filtered if replace else list(var.values) + filtered

        conflict_summary = detect_value_conflicts(merged)
        if conflict_summary.has_conflicts:
            dup_samples = []
            for idx, other in conflict_summary.duplicate_pairs[:5]:
                dup_samples.append(f"{merged[idx].name} == {merged[other].name}")
            subset_samples = []
            for idx, other in conflict_summary.subset_pairs[:5]:
                subset_samples.append(f"{merged[idx].name} <= {merged[other].name}")

            lines = [
                "중복/부분집합 태그가 있어 충돌이 발생합니다.",
                f"중복 쌍: {len(conflict_summary.duplicate_pairs)}개",
                f"부분집합 쌍: {len(conflict_summary.subset_pairs)}개",
            ]
            if dup_samples:
                lines.append("중복 예시: " + ", ".join(dup_samples))
            if subset_samples:
                lines.append("부분집합 예시: " + ", ".join(subset_samples))
            lines.append("충돌 항목을 자동으로 제외하고 계속할까요?")

            if not messagebox.askyesno("불러오기", "\n".join(lines)):
                return

            merged, conflict_summary = filter_value_conflicts(merged)
            if conflict_summary.removed_indices:
                messagebox.showinfo(
                    "불러오기",
                    f"충돌 항목 {len(conflict_summary.removed_indices)}개를 제외했습니다.",
                )
            if not merged:
                messagebox.showerror("불러오기", "남은 값이 없습니다.")
                return

        updated = Variable(name=var.name, values=merged)
        self._replace_variable(updated)
        self._refresh_values()
        logger.info("Imported %d values into %s", len(merged), var.name)

    def _remove_common_tags(self) -> None:
        var = self._get_selected_variable()
        if var is None:
            messagebox.showwarning("공통 태그 제외", "먼저 변수를 선택하세요.")
            return
        if not var.values:
            messagebox.showinfo("공통 태그 제외", "값이 없습니다.")
            return

        updated_values, common_tags = remove_common_tags_from_values(var.values)
        self.common_tags_by_var[var.name] = common_tags
        if not common_tags:
            messagebox.showinfo("공통 태그 제외", "공통 태그가 없습니다.")
            return

        conflict_summary = detect_value_conflicts(updated_values)
        if conflict_summary.has_conflicts:
            dup_samples = []
            for idx, other in conflict_summary.duplicate_pairs[:5]:
                dup_samples.append(
                    f"{updated_values[idx].name} == {updated_values[other].name}"
                )
            subset_samples = []
            for idx, other in conflict_summary.subset_pairs[:5]:
                subset_samples.append(
                    f"{updated_values[idx].name} <= {updated_values[other].name}"
                )
            lines = [
                "공통 태그 제외 후 중복/부분집합 태그가 있습니다.",
                f"중복 쌍: {len(conflict_summary.duplicate_pairs)}개",
                f"부분집합 쌍: {len(conflict_summary.subset_pairs)}개",
            ]
            if dup_samples:
                lines.append("중복 예시: " + ", ".join(dup_samples))
            if subset_samples:
                lines.append("부분집합 예시: " + ", ".join(subset_samples))
            lines.append("충돌 항목을 자동으로 제외하고 계속할까요?")
            if not messagebox.askyesno("공통 태그 제외", "\n".join(lines)):
                return
            updated_values, conflict_summary = filter_value_conflicts(updated_values)
            if conflict_summary.removed_indices:
                messagebox.showinfo(
                    "공통 태그 제외",
                    f"충돌 항목 {len(conflict_summary.removed_indices)}개를 제외했습니다.",
                )
            if not updated_values:
                messagebox.showerror("공통 태그 제외", "남은 값이 없습니다.")
                return

        updated = Variable(name=var.name, values=updated_values)
        self._replace_variable(updated)
        self._refresh_values()
        messagebox.showinfo("공통 태그 제외", f"공통 태그 {len(common_tags)}개를 제외했습니다.")

    def _show_common_tags(self) -> None:
        var = self._get_selected_variable()
        if var is None:
            messagebox.showwarning("공통 태그 보기", "먼저 변수를 선택하세요.")
            return

        cached = self.common_tags_by_var.get(var.name)
        if not cached:
            _updated, common_tags = remove_common_tags_from_values(var.values)
            self.common_tags_by_var[var.name] = common_tags
            cached = common_tags

        tags_text = ", ".join(cached)
        dialog = tk.Toplevel(self.app.root)
        dialog.title("공통 태그")
        dialog.transient(self.app.root)
        dialog.grab_set()

        ttk.Label(dialog, text=f"공통 태그 {len(cached)}개").pack(
            anchor="w", padx=10, pady=6
        )
        text = tk.Text(dialog, height=10, width=60)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        text.insert("1.0", tags_text)
        text.config(state="disabled")

        def copy_tags() -> None:
            self.app.root.clipboard_clear()
            self.app.root.clipboard_append(tags_text)

        btns = ttk.Frame(dialog)
        btns.pack(fill=tk.X, padx=10, pady=6)
        ttk.Button(btns, text="복사", command=copy_tags).pack(side=tk.LEFT)
        ttk.Button(btns, text="닫기", command=dialog.destroy).pack(side=tk.RIGHT)

    def _export_values(self) -> None:
        var = self._get_selected_variable()
        if var is None:
            messagebox.showwarning("내보내기", "먼저 변수를 선택하세요.")
            return
        try:
            payload = export_variable_to_nais(var)
        except ValueError as exc:
            messagebox.showerror("내보내기", str(exc))
            return
        filename = f"NAIS_{var.name}.json"
        path = filedialog.asksaveasfilename(
            title="NAIS 내보내기",
            defaultextension=".json",
            initialfile=filename,
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except Exception as exc:
            messagebox.showerror("내보내기", f"저장 실패: {exc}")
            return
        logger.info("Exported NAIS: %s", path)

    def _on_variable_select(self, _event: tk.Event) -> None:
        selection = self.variables_list.curselection()
        if not selection:
            return
        self.selected_variable_index = selection[0]
        self.selected_value_index = None
        self._refresh_values()
        self._load_variable_details()
        self._load_value_details(None)

    def _on_value_select(self, _event: tk.Event) -> None:
        selection = self.values_list.curselection()
        if not selection:
            return
        self.selected_value_index = selection[0]
        self._load_value_details(self.selected_value_index)

    def _refresh_variables(self) -> None:
        self.variables_list.delete(0, tk.END)
        for var in self.state.preset.variables:
            self.variables_list.insert(tk.END, var.name)
        if self.selected_variable_index is not None:
            try:
                self.variables_list.selection_set(self.selected_variable_index)
            except tk.TclError:
                pass

    def _refresh_values(self) -> None:
        self.values_list.delete(0, tk.END)
        var = self._get_selected_variable()
        if var is None:
            return
        for value in var.values:
            self.values_list.insert(tk.END, value.name)
        if self.selected_value_index is not None:
            try:
                self.values_list.selection_set(self.selected_value_index)
            except tk.TclError:
                pass

    def _load_variable_details(self) -> None:
        var = self._get_selected_variable()
        if var is None:
            self.variable_name_var.set("")
            return
        self.variable_name_var.set(var.name)

    def _load_value_details(self, idx: int | None) -> None:
        var = self._get_selected_variable()
        if var is None or idx is None:
            self.value_name_var.set("")
            self.value_tags_var.set("")
            return
        value = var.values[idx]
        self.value_name_var.set(value.name)
        self.value_tags_var.set(", ".join(value.tags))

    def _replace_variable(self, updated: Variable) -> None:
        idx = self.selected_variable_index
        if idx is None:
            return
        variables = list(self.state.preset.variables)
        variables[idx] = updated
        ok, error = self.state.replace_preset(variables, self.state.preset.name)
        if not ok:
            messagebox.showerror("검증", error)
            return
        self.app.on_preset_changed()

    def _get_selected_variable(self) -> Variable | None:
        if self.selected_variable_index is None:
            return None
        try:
            return self.state.preset.variables[self.selected_variable_index]
        except IndexError:
            return None

    def _bulk_apply_names(self, transform) -> None:
        var = self._get_selected_variable()
        if var is None:
            messagebox.showwarning("일괄 변경", "먼저 변수를 선택하세요.")
            return
        if not var.values:
            messagebox.showinfo("일괄 변경", "값이 없습니다.")
            return

        updated_values: list[VariableValue] = []
        for value in var.values:
            new_name = transform(value.name)
            if not new_name:
                messagebox.showerror("일괄 변경", "빈 이름이 생겨서 중단했습니다.")
                return
            updated_values.append(VariableValue(name=new_name, tags=value.tags))

        updated = Variable(name=var.name, values=updated_values)
        self._replace_variable(updated)
        self._refresh_values()

    def _bulk_add_prefix(self) -> None:
        prefix = self.bulk_prefix_var.get()
        if not prefix:
            messagebox.showwarning("일괄 변경", "앞에 추가할 단어를 입력하세요.")
            return
        self._bulk_apply_names(lambda name: f"{prefix}{name}")

    def _bulk_add_suffix(self) -> None:
        suffix = self.bulk_suffix_var.get()
        if not suffix:
            messagebox.showwarning("일괄 변경", "뒤에 추가할 단어를 입력하세요.")
            return
        self._bulk_apply_names(lambda name: f"{name}{suffix}")

    def _bulk_replace(self) -> None:
        target = self.bulk_find_var.get()
        if not target:
            messagebox.showwarning("일괄 변경", "바꿀 단어를 입력하세요.")
            return
        replacement = self.bulk_replace_var.get()
        self._bulk_apply_names(lambda name: name.replace(target, replacement))

    def _bulk_remove(self) -> None:
        target = self.bulk_remove_var.get()
        if not target:
            messagebox.showwarning("일괄 변경", "삭제할 단어를 입력하세요.")
            return
        self._bulk_apply_names(lambda name: name.replace(target, ""))
