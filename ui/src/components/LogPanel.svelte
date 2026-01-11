<script lang="ts">
  export let logs: string[] = [];

  function copyAll() {
    const text = logs.join("\n");
    navigator.clipboard.writeText(text).catch(() => undefined);
  }
</script>

<section class="panel footer">
  <div class="section-title">
    <h2>최근 로그</h2>
    <span class="badge">최대 100줄</span>
  </div>
  <div class="log-actions">
    <button class="ghost" on:click={copyAll}>복사</button>
  </div>
  <div class="log-list">
    {#if logs.length === 0}
      <div class="log-item">로그가 없습니다.</div>
    {:else}
      {#each logs as line}
        <div class="log-item">{line}</div>
      {/each}
    {/if}
  </div>
</section>
