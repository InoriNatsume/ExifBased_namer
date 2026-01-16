<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import { browseFolder, type BrowseItem } from "../lib/api";

  export let isOpen = false;
  export let title = "폴더 선택";

  const dispatch = createEventDispatcher<{ select: string }>();

  let currentPath = "";
  let parentPath: string | null = null;
  let items: BrowseItem[] = [];
  let loading = false;
  let error = "";

  $: if (isOpen) loadFolder("");

  async function loadFolder(path: string) {
    loading = true;
    error = "";
    try {
      const result = await browseFolder(path);
      currentPath = result.current;
      parentPath = result.parent;
      items = result.items.filter(i => i.type === "folder" || i.type === "drive");
    } catch (err) {
      error = `오류: ${err}`;
    } finally {
      loading = false;
    }
  }

  function handleSelect(item: BrowseItem) {
    if (item.type === "folder" || item.type === "drive") {
      loadFolder(item.path);
    }
  }

  function goUp() {
    if (parentPath !== null) {
      loadFolder(parentPath);
    } else {
      loadFolder("");
    }
  }

  function confirm() {
    if (currentPath) {
      dispatch("select", currentPath);
      isOpen = false;
    }
  }

  function close() {
    isOpen = false;
  }
</script>

{#if isOpen}
  <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
  <div class="overlay" on:click={close}>
    <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
    <div class="modal" on:click|stopPropagation>
      <div class="header">
        <span class="title">{title}</span>
        <button class="close-btn" on:click={close}>×</button>
      </div>

      <div class="path-bar">
        <button class="btn sm" on:click={goUp} disabled={!parentPath && !currentPath}>↑ 상위</button>
        <input class="path-input" value={currentPath} readonly placeholder="경로" />
      </div>

      <div class="content">
        {#if loading}
          <div class="loading">불러오는 중...</div>
        {:else if error}
          <div class="error">{error}</div>
        {:else if items.length === 0}
          <div class="empty">폴더가 없습니다</div>
        {:else}
          <ul class="folder-list">
            {#each items as item}
              <li on:dblclick={() => handleSelect(item)} on:click={() => handleSelect(item)}>
                <span class="icon">{item.type === "drive" ? "💾" : "📁"}</span>
                <span class="name">{item.name}</span>
              </li>
            {/each}
          </ul>
        {/if}
      </div>

      <div class="footer">
        <span class="selected">{currentPath || "선택된 폴더 없음"}</span>
        <div class="actions">
          <button class="btn primary" on:click={confirm} disabled={!currentPath}>선택</button>
          <button class="btn" on:click={close}>취소</button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
.overlay{position:fixed;inset:0;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;z-index:1000}
.modal{background:var(--panel);border-radius:var(--radius);width:500px;max-width:90vw;max-height:80vh;display:flex;flex-direction:column;box-shadow:0 8px 32px rgba(0,0,0,0.4)}
.header{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid rgba(255,255,255,0.06)}
.title{font-weight:600;font-size:14px}
.close-btn{background:none;border:none;color:var(--text-muted);font-size:20px;cursor:pointer}
.close-btn:hover{color:var(--text)}
.path-bar{display:flex;gap:8px;padding:10px 16px;border-bottom:1px solid rgba(255,255,255,0.06)}
.path-input{flex:1;padding:6px 10px;background:var(--bg);border:1px solid rgba(255,255,255,0.08);border-radius:6px;color:var(--text);font-size:12px}
.content{flex:1;overflow-y:auto;min-height:200px;max-height:400px}
.loading,.error,.empty{padding:40px;text-align:center;color:var(--text-muted)}
.error{color:var(--danger)}
.folder-list{list-style:none;margin:0;padding:4px}
.folder-list li{display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:6px;cursor:pointer}
.folder-list li:hover{background:var(--bg)}
.folder-list li .icon{font-size:16px}
.folder-list li .name{font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.footer{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-top:1px solid rgba(255,255,255,0.06);gap:12px}
.selected{font-size:11px;color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
.actions{display:flex;gap:8px}
.btn{padding:6px 12px;background:var(--panel-2);border:none;border-radius:6px;color:var(--text);font-size:12px;font-weight:600;cursor:pointer}
.btn:hover{background:var(--bg)}
.btn:disabled{opacity:0.5;cursor:not-allowed}
.btn.sm{padding:4px 10px;font-size:11px}
.btn.primary{background:var(--accent);color:var(--bg)}
</style>
