<script lang="ts">
  import type { ConflictSummary, Preset, PresetValue } from "../lib/preset";
  import {
    detectConflicts,
    normalizeTagText,
    normalizeTags,
    removeCommonTags,
  } from "../lib/preset";
  import BuildPanel from "./editor/BuildPanel.svelte";
  import PresetFilePanel from "./editor/PresetFilePanel.svelte";
  import PresetImportPanel, {
    type ImportMode,
  } from "./editor/PresetImportPanel.svelte";
  import TagEditor from "./editor/TagEditor.svelte";
  import ValueList, { type BulkAction } from "./editor/ValueList.svelte";
  import VariableList from "./editor/VariableList.svelte";

  export type BuildMode = "replace" | "append";

  export let preset: Preset;
  export let presetPath: string | null = null;
  export let presetStatus = "";
  export let onChange: (preset: Preset) => void;
  export let onBuild: (payload: {
    folder: string;
    includeNegative: boolean;
    targetName: string;
    mode: BuildMode;
  }) => void;
  export let onPresetLoad: (path: string) => void;
  export let onPresetSave: (path: string) => void;
  export let onPresetClear: () => void;
  export let onPresetImport: (
    path: string,
    mode: ImportMode,
    variableName: string
  ) => void;
  export let buildStatus = "";
  export let buildStats: Record<string, unknown> | null = null;
  export let buildCommonTags: string[] = [];

  let selectedVariableIndex: number | null = null;
  let selectedValueIndex: number | null = null;
  let valueTags = "";
  let variableCommonTags: string[] = [];
  let conflictSummary: ConflictSummary | null = null;
  let lastSelectedVariableIndex: number | null = null;
  let lastSelectedValueIndex: number | null = null;

  $: selectedVariable =
    selectedVariableIndex !== null
      ? preset.variables[selectedVariableIndex]
      : null;
  $: selectedValue =
    selectedVariable && selectedValueIndex !== null
      ? selectedVariable.values[selectedValueIndex]
      : null;

  $: if (
    selectedVariableIndex !== null &&
    selectedVariableIndex >= preset.variables.length
  ) {
    selectedVariableIndex = null;
  }

  $: if (
    selectedValueIndex !== null &&
    selectedVariable &&
    selectedValueIndex >= selectedVariable.values.length
  ) {
    selectedValueIndex = null;
  }

  $: if (selectedVariableIndex !== lastSelectedVariableIndex) {
    lastSelectedVariableIndex = selectedVariableIndex;
    selectedValueIndex = null;
    lastSelectedValueIndex = null;
    valueTags = "";
  }

  $: if (selectedValueIndex !== lastSelectedValueIndex) {
    lastSelectedValueIndex = selectedValueIndex;
    valueTags = selectedValue ? selectedValue.tags.join(", ") : "";
  } else if (selectedValue) {
    const tagsText = selectedValue.tags.join(", ");
    if (valueTags !== tagsText) {
      valueTags = tagsText;
    }
  }

  function makeUniqueName(base: string, existing: Set<string>): string {
    let name = base;
    let idx = 2;
    while (existing.has(name)) {
      name = `${base} ${idx}`;
      idx += 1;
    }
    return name;
  }

  function addVariable() {
    const existing = new Set(preset.variables.map((variable) => variable.name));
    const name = makeUniqueName("새 변수", existing);
    const vars = [...preset.variables, { name, values: [] }];
    preset = { ...preset, variables: vars };
    onChange(preset);
    selectedVariableIndex = vars.length - 1;
  }

  function deleteVariable() {
    if (selectedVariableIndex === null) {
      return;
    }
    const vars = [...preset.variables];
    vars.splice(selectedVariableIndex, 1);
    preset = { ...preset, variables: vars };
    onChange(preset);
    selectedVariableIndex = null;
    selectedValueIndex = null;
    valueTags = "";
    variableCommonTags = [];
    conflictSummary = null;
  }

  function applyVariableNameAt(index: number, name: string) {
    const cleaned = name.trim();
    if (!cleaned) {
      return;
    }
    const duplicate = preset.variables.some(
      (variable, idx) => idx !== index && variable.name === cleaned
    );
    if (duplicate) {
      alert("이미 존재하는 변수 이름입니다.");
      return;
    }
    const vars = [...preset.variables];
    vars[index] = {
      ...vars[index],
      name: cleaned,
    };
    preset = { ...preset, variables: vars };
    onChange(preset);
  }

  function addValue() {
    if (!selectedVariable) {
      return;
    }
    const existing = new Set(selectedVariable.values.map((value) => value.name));
    const name = makeUniqueName("새 값", existing);
    const values = [...selectedVariable.values, { name, tags: [] }];
    updateVariable({ ...selectedVariable, values });
    selectedValueIndex = values.length - 1;
  }

  function deleteValue() {
    if (!selectedVariable || selectedValueIndex === null) {
      return;
    }
    const values = [...selectedVariable.values];
    values.splice(selectedValueIndex, 1);
    updateVariable({ ...selectedVariable, values });
    selectedValueIndex = null;
    valueTags = "";
  }

  function applyValueNameAt(index: number, name: string) {
    if (!selectedVariable) {
      return;
    }
    const cleaned = name.trim();
    if (!cleaned) {
      return;
    }
    const values = [...selectedVariable.values];
    if (index < 0 || index >= values.length) {
      return;
    }
    values[index] = {
      ...values[index],
      name: cleaned,
    };
    updateVariable({ ...selectedVariable, values });
  }

  function applyValueTags(text: string) {
    if (!selectedVariable || selectedValueIndex === null) {
      return;
    }
    const tags = normalizeTags(normalizeTagText(text.replace(/\n/g, ",")));
    const values = [...selectedVariable.values];
    values[selectedValueIndex] = {
      ...values[selectedValueIndex],
      tags,
    };
    updateVariable({ ...selectedVariable, values });
    valueTags = tags.join(", ");
  }

  function updateVariable(updated: { name: string; values: PresetValue[] }) {
    if (selectedVariableIndex === null) {
      return;
    }
    const vars = [...preset.variables];
    vars[selectedVariableIndex] = updated;
    preset = { ...preset, variables: vars };
    onChange(preset);
  }

  function selectVariable(index: number) {
    selectedVariableIndex = index;
    selectedValueIndex = null;
    variableCommonTags = [];
    conflictSummary = null;
  }

  function selectValue(index: number) {
    selectedValueIndex = index;
  }

  function removeCommon() {
    if (!selectedVariable) {
      return;
    }
    const result = removeCommonTags(selectedVariable.values);
    variableCommonTags = result.common;
    updateVariable({ ...selectedVariable, values: result.values });
  }

  function checkConflicts() {
    if (!selectedVariable) {
      return;
    }
    conflictSummary = detectConflicts(selectedVariable.values);
  }

  function removeTagsFromAll(text: string) {
    if (!selectedVariable) {
      alert("먼저 변수를 선택하세요.");
      return;
    }
    const targets = normalizeTags(normalizeTagText(text.replace(/\n/g, ",")));
    if (targets.length === 0) {
      alert("삭제할 태그를 입력하세요.");
      return;
    }
    const targetSet = new Set(targets);
    const updatedValues = selectedVariable.values.map((value) => ({
      ...value,
      tags: value.tags.filter((tag) => !targetSet.has(tag)),
    }));
    updateVariable({ ...selectedVariable, values: updatedValues });
  }

  function bulkApply(action: BulkAction) {
    if (!selectedVariable) {
      alert("먼저 변수를 선택하세요.");
      return;
    }
    if (selectedVariable.values.length === 0) {
      alert("값이 없습니다.");
      return;
    }
    let transform: (name: string) => string;
    switch (action.type) {
      case "prefix":
        transform = (name) => `${action.value}${name}`;
        break;
      case "suffix":
        transform = (name) => `${name}${action.value}`;
        break;
      case "replace":
        transform = (name) => name.replace(action.find, action.replace);
        break;
      case "remove":
        transform = (name) => name.replace(action.value, "");
        break;
      default:
        return;
    }
    try {
      const updatedValues = selectedVariable.values.map((value) => {
        const nextName = transform(value.name).trim();
        if (!nextName) {
          throw new Error("이름이 비어 있습니다.");
        }
        return { ...value, name: nextName };
      });
      updateVariable({ ...selectedVariable, values: updatedValues });
    } catch (error) {
      alert(String(error));
    }
  }

  function importPreset(path: string, mode: ImportMode) {
    if (!selectedVariable) {
      alert("먼저 변수를 선택하세요.");
      return;
    }
    onPresetImport(path, mode, selectedVariable.name);
  }
</script>

<section class="panel">
  <div class="section-title">
    <h2>편집</h2>
    <span class="badge">템플릿</span>
  </div>
  <div class="input-row">
    <input bind:value={preset.name} placeholder="템플릿 이름" />
    <button class="primary" on:click={() => onChange(preset)}>이름 적용</button>
  </div>

  <PresetFilePanel
    {preset}
    lastPath={presetPath}
    status={presetStatus}
    onLoad={onPresetLoad}
    onSave={onPresetSave}
    onClear={onPresetClear}
  />

  <div class="editor-grid">
    <VariableList
      variables={preset.variables}
      selectedIndex={selectedVariableIndex}
      onSelect={selectVariable}
      onAdd={addVariable}
      onDelete={deleteVariable}
      onRename={applyVariableNameAt}
    />
    <ValueList
      values={selectedVariable ? selectedVariable.values : null}
      selectedIndex={selectedValueIndex}
      onSelect={selectValue}
      onAdd={addValue}
      onDelete={deleteValue}
      onRename={applyValueNameAt}
      onBulkApply={bulkApply}
    />
  </div>

  <PresetImportPanel
    variableName={selectedVariable?.name ?? null}
    onImport={importPreset}
  />

  <TagEditor
    {selectedVariable}
    {selectedValue}
    {valueTags}
    onApplyTags={applyValueTags}
    onRemoveCommon={removeCommon}
    onCheckConflicts={checkConflicts}
    onRemoveTagsFromAll={removeTagsFromAll}
    commonTags={variableCommonTags}
    {conflictSummary}
  />

  <BuildPanel
    variables={preset.variables}
    onBuild={onBuild}
    {buildStatus}
    {buildStats}
    {buildCommonTags}
  />
</section>
