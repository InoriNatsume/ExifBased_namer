<script lang="ts">
  import type { PresetVariable } from "../../lib/preset";

  export let variables: PresetVariable[] = [];
  export let selectedIndex: number | null = null;
  export let onSelect: (index: number) => void;
  export let onAdd: () => void;
  export let onDelete: () => void;
  export let onRename: (index: number, name: string) => void;

  function handleRename(index: number, event: Event) {
    const target = event.currentTarget as HTMLInputElement | null;
    if (!target) {
      return;
    }
    onRename(index, target.value);
  }
</script>

<div class="panel inner">
  <div class="section-title small">
    <h3>변수 목록</h3>
    <span class="badge">{variables.length}개</span>
  </div>
  <div class="list">
    {#each variables as variable, index}
      <div
        class="list-row"
        class:active={selectedIndex === index}
        on:click={() => onSelect(index)}
      >
        <input
          value={variable.name}
          on:focus={() => onSelect(index)}
          on:change={(event) => handleRename(index, event)}
        />
        <span class="muted">({variable.values.length})</span>
      </div>
    {/each}
  </div>
  <div class="row">
    <button class="ghost" on:click={onAdd}>추가</button>
    <button class="ghost" on:click={onDelete} disabled={selectedIndex === null}>
      삭제
    </button>
  </div>
</div>
