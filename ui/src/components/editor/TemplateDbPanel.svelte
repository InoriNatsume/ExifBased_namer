<script lang="ts">
  import type { TemplateInfo } from "../../lib/dbModels";

  export let items: TemplateInfo[] = [];
  export let selectedName: string | null = null;
  export let status = "";
  export let onRefresh: () => void;
  export let onLoad: (name: string) => void;
  export let onSave: () => void;
  export let onDelete: (name: string) => void;

  let selected = "";

  $: if (selectedName && selectedName !== selected) {
    selected = selectedName;
  }

  function loadSelected() {
    if (!selected) {
      alert("불러올 템플릿을 선택하세요.");
      return;
    }
    onLoad(selected);
  }

  function deleteSelected() {
    if (!selected) {
      alert("삭제할 템플릿을 선택하세요.");
      return;
    }
    onDelete(selected);
  }
</script>

<div class="panel inner">
  <div class="section-title small">
    <h3>템플릿(DB)</h3>
  </div>
  <div class="row compact">
    <select bind:value={selected}>
      <option value="">저장된 템플릿 선택</option>
      {#each items as item}
        <option value={item.name}>{item.name}</option>
      {/each}
    </select>
    <button class="ghost" on:click={onRefresh}>새로고침</button>
    <button class="ghost" on:click={loadSelected}>불러오기</button>
    <button class="ghost" on:click={deleteSelected} disabled={!selected}>삭제</button>
    <button class="primary" on:click={onSave}>저장</button>
  </div>
  {#if status}
    <div class="muted small">{status}</div>
  {/if}
</div>
