<script lang="ts">
  import { onMount } from "svelte";
  import { connectSidecar, runSidecarJob, isTauri } from "./lib/ipc";
  import type { IpcMessage, IpcRunRequest } from "./lib/types";

  const tabs = ["편집", "검색", "파일명 변경", "폴더 분류"] as const;
  let active = tabs[1];
  let status = "대기";
  let folder = "";
  let tags = "";
  let logs: string[] = [];
  let results: string[] = [];
  let tauriMode = false;

  function appendLog(line: string) {
    logs = [line, ...logs].slice(0, 50);
  }

  function onMessage(message: IpcMessage) {
    if (message.type === "log") {
      appendLog(message.message ?? "로그 수신");
      return;
    }
    if (message.type === "progress") {
      status = `진행: ${message.processed ?? 0}/${message.total ?? 0}`;
      return;
    }
    if (message.type === "result") {
      if (message.source) {
        results = [`${message.status ?? "OK"} | ${message.source}`, ...results].slice(
          0,
          100
        );
      }
      return;
    }
    if (message.type === "done") {
      status = "완료";
      return;
    }
    if (message.type === "error") {
      status = `오류: ${message.message ?? "알 수 없음"}`;
      return;
    }
  }

  async function runSearch() {
    if (!tauriMode) {
      status = "브라우저 모드에서는 IPC를 실행할 수 없습니다.";
      return;
    }
    const request: IpcRunRequest = {
      id: `ui-${Date.now()}`,
      type: "run",
      op: "search",
      payload: { folder, tags, include_negative: false, progress_step: 200 },
    };
    status = "요청 전송 중...";
    try {
      await runSidecarJob(request);
    } catch (error) {
      status = `오류: ${String(error)}`;
    }
  }

  function prepScan() {
    if (!tauriMode) {
      status = "브라우저 모드에서는 IPC를 실행할 수 없습니다.";
      return;
    }
    status = "DB 스캔 준비";
  }

  onMount(async () => {
    tauriMode = isTauri();
    if (!tauriMode) {
      status = "브라우저 모드";
    }
    try {
      await connectSidecar(onMessage);
      appendLog("IPC 연결 준비 완료");
    } catch (error) {
      status = "IPC 연결 실패";
      appendLog(String(error));
    }
  });
</script>

<div class="app">
  <aside class="sidebar">
    <div class="brand">
      <h1>NAI 태그 분류기</h1>
      <span>Sidecar + Svelte/Tauri</span>
    </div>
    <nav class="nav">
      {#each tabs as tab}
        <button class:active={active === tab} on:click={() => (active = tab)}>
          {tab}
        </button>
      {/each}
    </nav>
  </aside>

  <main class="main">
    <section class="panel">
      <div class="section-title">
        <h2>{active}</h2>
        <span class="badge">{tauriMode ? "IPC 준비" : "브라우저"}</span>
      </div>
      <div class="input-row">
        <input bind:value={folder} placeholder="작업 폴더 경로" />
        <button class="primary" on:click={runSearch}>검색 테스트</button>
      </div>
      <div class="input-row">
        <input bind:value={tags} placeholder="필수 태그 (쉼표 구분)" />
        <button class="primary" on:click={prepScan}>DB 스캔</button>
      </div>
      <p>상태: {status}</p>
    </section>

    <section class="panel">
      <div class="section-title">
        <h2>결과</h2>
        <span class="badge">미리보기 예정</span>
      </div>
      <div class="result-list">
        {#if results.length === 0}
          <div class="result-item">결과가 없습니다.</div>
        {:else}
          {#each results as item}
            <div class="result-item">
              <span>{item}</span>
              <span>...</span>
            </div>
          {/each}
        {/if}
      </div>
    </section>

    <section class="panel footer">
      <strong>최근 로그</strong>
      {#each logs as line}
        <span>{line}</span>
      {/each}
    </section>
  </main>
</div>
