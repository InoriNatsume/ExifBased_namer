<script lang="ts">
  export let processed = 0;
  export let total = 0;
  export let status = "";
  export let detail = "";
  export let label = "진행";

  $: hasTotal = total > 0;
  $: percent = hasTotal ? Math.min(100, Math.round((processed / total) * 100)) : 0;
</script>

<div class="progress-panel">
  <div class="progress-header">
    <span class="progress-title">{label}</span>
    {#if status}
      <span class="muted">{status}</span>
    {/if}
  </div>
  <div class="progress-track">
    <div class="progress-fill" style={`width: ${percent}%`}></div>
  </div>
  <div class="progress-meta">
    {#if hasTotal}
      <span class="progress-count">{processed}/{total} ({percent}%)</span>
    {:else}
      <span class="progress-count">진행 정보 없음</span>
    {/if}
    {#if detail}
      <span class="muted">{detail}</span>
    {/if}
  </div>
</div>
