<script lang="ts">
  import type {
    ConflictSummary,
    PresetValue,
    PresetVariable,
  } from "../../lib/preset";

  export let selectedVariable: PresetVariable | null = null;
  export let selectedValue: PresetValue | null = null;
  export let valueTags = "";
  export let onApplyTags: (text: string) => void;
  export let onRemoveCommon: () => void;
  export let onCheckConflicts: () => void;
  export let onRemoveTagsFromAll: (text: string) => void;
  export let commonTags: string[] = [];
  export let conflictSummary: ConflictSummary | null = null;

  let localTags = "";
  let bulkRemoveText = "";
  let subsetLines: string[] = [];
  let duplicateLines: string[] = [];
  let isEditing = false;
  let lastSelectedName = "";

  $: if (!selectedValue) {
    localTags = "";
    isEditing = false;
    lastSelectedName = "";
  }

  $: if (selectedValue && selectedValue.name !== lastSelectedName) {
    lastSelectedName = selectedValue.name;
    isEditing = false;
    localTags = valueTags;
  }

  $: if (selectedValue && !isEditing && valueTags !== localTags) {
    localTags = valueTags;
  }

  $: subsetLines =
    conflictSummary?.subsets.map(([a, b]) => `${a} ⊆ ${b}`) ?? [];
  $: duplicateLines =
    conflictSummary?.duplicates.map(([a, b]) => `${a} == ${b}`) ?? [];

  function copyText(value: string) {
    navigator.clipboard.writeText(value).catch(() => undefined);
  }

  function applyTags() {
    onApplyTags(localTags);
    isEditing = false;
  }
</script>

<div class="panel inner tag-panel">
  <div class="section-title small">
    <h3>태그 편집</h3>
  </div>
  {#if !selectedVariable}
    <div class="muted">변수와 값을 클릭해서 편집하세요.</div>
  {:else}
    {#if selectedValue}
      <div class="muted">선택된 값: {selectedValue.name}</div>
      <label class="field">
        값 태그
        <textarea
          bind:value={localTags}
          rows="8"
          placeholder="쉼표 또는 줄바꿈으로 구분"
          on:focus={() => (isEditing = true)}
        ></textarea>
      </label>
      <div class="row">
        <button class="ghost" on:click={applyTags}>태그 적용</button>
      </div>
    {:else}
      <div class="muted">값을 선택하세요.</div>
    {/if}
    <div class="row">
      <button class="ghost" on:click={onRemoveCommon} disabled={!selectedVariable}>
        공통 태그 제외
      </button>
      <button class="ghost" on:click={onCheckConflicts} disabled={!selectedVariable}>
        충돌 검사
      </button>
    </div>
    <div class="field">
      <div class="field-header">
        <span>모든 값에서 태그 삭제</span>
      </div>
      <div class="bulk-row">
        <input bind:value={bulkRemoveText} placeholder="쉼표 또는 줄바꿈" />
        <button class="ghost" on:click={() => onRemoveTagsFromAll(bulkRemoveText)}>
          삭제
        </button>
      </div>
    </div>
  {/if}
  {#if commonTags.length > 0}
    <div class="field">
      <div class="field-header">
        <span>변수 공통 태그</span>
        <button class="ghost small" on:click={() => copyText(commonTags.join(", "))}>
          복사
        </button>
      </div>
      <textarea readonly rows="3">{commonTags.join(", ")}</textarea>
    </div>
  {/if}
  {#if conflictSummary}
    <div class="field">
      <div class="muted">
        중복 {duplicateLines.length}건, 부분집합 {subsetLines.length}건
      </div>
      {#if subsetLines.length > 0}
        <div class="field-header">
          <span>부분집합 목록(최대 10개)</span>
          <button class="ghost small" on:click={() => copyText(subsetLines.join("\n"))}>
            목록 복사
          </button>
        </div>
        <textarea readonly rows="4">{subsetLines.slice(0, 10).join("\n")}</textarea>
      {/if}
      {#if duplicateLines.length > 0}
        <div class="field-header">
          <span>중복 목록(최대 10개)</span>
          <button
            class="ghost small"
            on:click={() => copyText(duplicateLines.join("\n"))}
          >
            목록 복사
          </button>
        </div>
        <textarea readonly rows="3">{duplicateLines.slice(0, 10).join("\n")}</textarea>
      {/if}
    </div>
  {/if}
</div>
