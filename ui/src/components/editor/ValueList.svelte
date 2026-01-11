<script lang="ts">
  import type { PresetValue } from "../../lib/preset";

  export type BulkAction =
    | { type: "prefix"; value: string }
    | { type: "suffix"; value: string }
    | { type: "replace"; find: string; replace: string }
    | { type: "remove"; value: string };

  export let values: PresetValue[] | null = null;
  export let selectedIndex: number | null = null;
  export let onSelect: (index: number) => void;
  export let onAdd: () => void;
  export let onDelete: () => void;
  export let onRename: (index: number, name: string) => void;
  export let onBulkApply: (action: BulkAction) => void;

  let prefix = "";
  let suffix = "";
  let findText = "";
  let replaceText = "";
  let removeText = "";

  function handleRename(index: number, event: Event) {
    const target = event.currentTarget as HTMLInputElement | null;
    if (!target) {
      return;
    }
    onRename(index, target.value);
  }

  function applyPrefix() {
    if (!prefix.trim()) {
      alert("앞에 추가할 단어를 입력하세요.");
      return;
    }
    onBulkApply({ type: "prefix", value: prefix });
  }

  function applySuffix() {
    if (!suffix.trim()) {
      alert("뒤에 추가할 단어를 입력하세요.");
      return;
    }
    onBulkApply({ type: "suffix", value: suffix });
  }

  function applyReplace() {
    if (!findText.trim()) {
      alert("찾을 단어를 입력하세요.");
      return;
    }
    onBulkApply({ type: "replace", find: findText, replace: replaceText });
  }

  function applyRemove() {
    if (!removeText.trim()) {
      alert("삭제할 단어를 입력하세요.");
      return;
    }
    onBulkApply({ type: "remove", value: removeText });
  }
</script>

<div class="panel inner">
  <div class="section-title small">
    <h3>값 목록</h3>
    {#if values}
      <span class="badge">{values.length}개</span>
    {/if}
  </div>
  <div class="list">
    {#if values}
      {#each values as value, index}
        <div
          class="list-row"
          class:active={selectedIndex === index}
          on:click={() => onSelect(index)}
        >
          <input
            value={value.name}
            on:focus={() => onSelect(index)}
            on:change={(event) => handleRename(index, event)}
          />
          <span class="muted">({value.tags.length})</span>
        </div>
      {/each}
    {:else}
      <div class="muted">변수를 선택하세요.</div>
    {/if}
  </div>
  <div class="row">
    <button class="ghost" on:click={onAdd} disabled={!values}>추가</button>
    <button class="ghost" on:click={onDelete} disabled={!values || selectedIndex === null}>
      삭제
    </button>
  </div>

  <div class="bulk-panel">
    <div class="section-title small">
      <h4>값 이름 일괄 변경</h4>
    </div>
    <div class="bulk-row">
      <input bind:value={prefix} placeholder="앞에 추가" />
      <button class="ghost" on:click={applyPrefix} disabled={!values}>적용</button>
    </div>
    <div class="bulk-row">
      <input bind:value={suffix} placeholder="뒤에 추가" />
      <button class="ghost" on:click={applySuffix} disabled={!values}>적용</button>
    </div>
    <div class="bulk-row double">
      <input bind:value={findText} placeholder="찾기" />
      <input bind:value={replaceText} placeholder="바꾸기" />
      <button class="ghost" on:click={applyReplace} disabled={!values}>적용</button>
    </div>
    <div class="bulk-row">
      <input bind:value={removeText} placeholder="삭제할 단어" />
      <button class="ghost" on:click={applyRemove} disabled={!values}>적용</button>
    </div>
  </div>
</div>
