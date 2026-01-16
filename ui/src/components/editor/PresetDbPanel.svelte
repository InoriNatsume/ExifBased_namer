<script lang="ts">
  import type { PresetInfo } from "../../lib/dbModels";
  import type { PresetValue } from "../../lib/preset";
  import type { ImportMode } from "./PresetImportPanel.svelte";

  export let variableName: string | null = null;
  export let values: PresetValue[] = [];
  export let presets: PresetInfo[] = [];
  export let status = "";
  export let onRefresh: (variableName: string | null) => void;
  export let onApply: (presetId: number, mode: ImportMode, variableName: string) => void;
  export let onSave: (payload: {
    name: string;
    sourceKind: string;
    variableName: string;
    values: PresetValue[];
  }) => void;
  export let onDelete: (presetId: number) => void;

  let selectedId = "";
  let mode: ImportMode = "replace";
  let saveName = "";
  let sourceKind = "manual";

  function refresh() {
    onRefresh(variableName);
  }

  function applyPreset() {
    if (!variableName) {
      alert("변수를 선택하세요.");
      return;
    }
    if (!selectedId) {
      alert("프리셋을 선택하세요.");
      return;
    }
    onApply(Number(selectedId), mode, variableName);
  }

  function deletePreset() {
    if (!selectedId) {
      alert("삭제할 프리셋을 선택하세요.");
      return;
    }
    onDelete(Number(selectedId));
  }

  function savePreset() {
    if (!variableName) {
      alert("변수를 선택하세요.");
      return;
    }
    if (!saveName.trim()) {
      alert("프리셋 이름을 입력하세요.");
      return;
    }
    if (values.length === 0) {
      alert("저장할 값이 없습니다.");
      return;
    }
    onSave({
      name: saveName.trim(),
      sourceKind,
      variableName,
      values,
    });
  }
</script>

<div class="panel inner">
  <div class="section-title small">
    <h3>프리셋(DB)</h3>
  </div>
  <div class="muted">대상 변수: {variableName ?? "선택되지 않음"}</div>
  <div class="row compact">
    <select bind:value={selectedId}>
      <option value="">저장된 프리셋 선택</option>
      {#each presets as preset}
        <option value={preset.id}>
          {preset.name} ({preset.source_kind})
        </option>
      {/each}
    </select>
    <button class="ghost" on:click={refresh}>새로고침</button>
    <button class="ghost" on:click={applyPreset}>적용</button>
    <button class="ghost" on:click={deletePreset} disabled={!selectedId}>삭제</button>
  </div>
  <div class="toggle-row">
    <label>
      <input type="radio" bind:group={mode} value="replace" />
      덮어쓰기
    </label>
    <label>
      <input type="radio" bind:group={mode} value="append" />
      기존 값에 추가
    </label>
  </div>
  <div class="row compact">
    <input bind:value={saveName} placeholder="프리셋 이름" />
    <select bind:value={sourceKind}>
      <option value="manual">manual</option>
      <option value="nais">nais</option>
      <option value="sdstudio">sdstudio</option>
      <option value="folder">folder</option>
    </select>
    <button class="primary" on:click={savePreset}>저장</button>
  </div>
  {#if status}
    <div class="muted small">{status}</div>
  {/if}
</div>
