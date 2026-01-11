<script lang="ts">
  import { convertFileSrc } from "@tauri-apps/api/core";
  import { isTauri } from "../lib/ipc";
  import type { ResultRecord, ResultStatus } from "../lib/models";

  export let records: ResultRecord[] = [];
  export let title = "결과";
  export let limit = 2000;

  const statuses: ResultStatus[] = ["OK", "UNKNOWN", "CONFLICT", "ERROR", "SKIP"];
  let filters: Record<ResultStatus, boolean> = {
    OK: true,
    UNKNOWN: true,
    CONFLICT: true,
    ERROR: true,
    SKIP: false,
  };
  let selectedId: string | null = null;

  $: filtered = records.filter((record) => filters[record.status]).slice(0, limit);
  $: selected = filtered.find((record) => record.id === selectedId) ?? null;
  $: tauriMode = isTauri();
  $: previewUrl =
    selected && selected.preview && tauriMode
      ? convertFileSrc(selected.preview.replace(/\\/g, "/"))
      : "";

  function select(record: ResultRecord) {
    selectedId = record.id;
  }
</script>

<section class="panel">
  <div class="section-title">
    <h2>{title}</h2>
    <span class="badge">미리보기 예정</span>
  </div>
  <div class="filter-row">
    {#each statuses as status}
      <label>
        <input type="checkbox" bind:checked={filters[status]} /> {status}
      </label>
    {/each}
  </div>
  <div class="result-grid">
    <div class="result-list">
      {#if filtered.length === 0}
        <div class="result-item empty">결과가 없습니다.</div>
      {:else}
        {#each filtered as item}
          <button
            type="button"
            class:active={selectedId === item.id}
            class="result-item"
            on:click={() => select(item)}
          >
            <span>{item.text}</span>
          </button>
        {/each}
      {/if}
    </div>
    <div class="preview">
      {#if !selected}
        <div class="preview-empty">미리보기 없음</div>
      {:else if !selected.preview}
        <div class="preview-empty">미리보기 없음</div>
      {:else if !tauriMode}
        <div class="preview-empty">브라우저 모드에서는 미리보기가 비활성입니다.</div>
      {:else}
        <img alt="preview" src={previewUrl} />
      {/if}
      {#if selected?.preview}
        <div class="preview-path">{selected.preview}</div>
      {/if}
    </div>
  </div>
</section>
