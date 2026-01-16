<script lang="ts">
  import { onMount } from "svelte";
  import {
    activeTab,
    jobState,
    template,
    logs,
    appendLog,
  } from "./lib/stores";
  import { cancelJob, getDbStats, listTemplates } from "./lib/api";
  import type { IpcMessage } from "./lib/types";
  import EditorPanel from "./components/EditorPanel.svelte";
  import RenamePanel from "./components/RenamePanel.svelte";
  import MovePanel from "./components/MovePanel.svelte";

  // Local state
  let dbStats = { images: 0, tags: 0, matches: 0 };
  let templateList: Array<{ name: string }> = [];

  // Reactive
  $: progressPercent =
    $jobState.total > 0
      ? Math.round(($jobState.processed / $jobState.total) * 100)
      : 0;

  onMount(async () => {
    try {
      dbStats = await getDbStats();
      templateList = await listTemplates();
      appendLog(`DB: ${dbStats.images} 이미지, ${dbStats.tags} 태그`);
    } catch (err) {
      appendLog(`초기화 오류: ${err}`);
    }
  });

  function handleMessage(message: IpcMessage) {
    if (message.type === "progress") {
      jobState.update((s) => ({
        ...s,
        processed: message.processed,
        total: message.total,
        errors: message.errors,
        skipped: message.skipped ?? s.skipped,
      }));
    } else if (message.type === "done") {
      jobState.update((s) => ({
        ...s,
        active: false,
        status: message.cancelled ? "취소됨" : "완료",
      }));
      appendLog(`작업 완료: ${$jobState.processed}건 처리`);
    } else if (message.type === "error") {
      appendLog(`오류: ${message.message}`);
      jobState.update((s) => ({ ...s, active: false, status: "오류" }));
    } else if (message.type === "log") {
      appendLog(message.message);
    }
  }

  async function handleCancel() {
    if ($jobState.jobId) {
      await cancelJob($jobState.jobId);
      appendLog("취소 요청됨");
    }
  }

  function setTab(tab: "editor" | "rename" | "move") {
    activeTab.set(tab);
  }
</script>

<div class="app-shell">
  <aside class="sidebar">
    <div class="brand">NAI Tag Classifier</div>
    <div class="subtitle">DB: {dbStats.images} 이미지</div>

    <div class="nav-group">
      <div class="nav-title">Tasks</div>
      <ul class="nav-list">
        <li
          class="nav-item"
          class:active={$activeTab === "editor"}
          on:click={() => setTab("editor")}
          on:keydown={(e) => e.key === "Enter" && setTab("editor")}
          role="button"
          tabindex="0"
        >
          Editor
        </li>
        <li
          class="nav-item"
          class:active={$activeTab === "rename"}
          on:click={() => setTab("rename")}
          on:keydown={(e) => e.key === "Enter" && setTab("rename")}
          role="button"
          tabindex="0"
        >
          Rename
        </li>
        <li
          class="nav-item"
          class:active={$activeTab === "move"}
          on:click={() => setTab("move")}
          on:keydown={(e) => e.key === "Enter" && setTab("move")}
          role="button"
          tabindex="0"
        >
          분류
        </li>
      </ul>
    </div>

    {#if $jobState.active}
      <div class="progress-section">
        <div class="progress-label">{$jobState.status}</div>
        <div class="progress-bar">
          <div class="progress-fill" style="width: {progressPercent}%"></div>
        </div>
        <div class="progress-text">
          {$jobState.processed}/{$jobState.total} ({progressPercent}%)
        </div>
        <button class="btn danger small" on:click={handleCancel}>취소</button>
      </div>
    {/if}
  </aside>

  <main class="main">
    {#if $activeTab === "editor"}
      <!-- Editor Tab -->
      <section class="topbar">
        <div>
          <h2>템플릿 편집</h2>
        </div>
      </section>
      <section class="content editor-content">
        <EditorPanel />
      </section>
    {:else if $activeTab === "rename"}
      <!-- Rename Tab -->
      <section class="panel-full">
        <RenamePanel />
      </section>
    {:else if $activeTab === "move"}
      <!-- Move Tab -->
      <section class="panel-full">
        <MovePanel />
      </section>
    {/if}
  </main>
</div>

