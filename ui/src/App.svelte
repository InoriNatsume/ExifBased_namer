<script lang="ts">
  import { onMount } from "svelte";
  import { connectSidecar, isTauri, runSidecarJob } from "./lib/ipc";
  import type { IpcMessage, IpcRunRequest } from "./lib/types";
  import {
    formatEta,
    type JobMode,
    type JobProgress,
    type JobStats,
    type ResultRecord,
    type ResultStatus,
  } from "./lib/models";
  import { normalizeTags, type Preset, type PresetValue } from "./lib/preset";
  import EditorView from "./components/EditorView.svelte";
  import SearchView from "./components/SearchView.svelte";
  import ResultPanel from "./components/ResultPanel.svelte";
  import LogPanel from "./components/LogPanel.svelte";

  const tabs = [
    { id: "editor", label: "편집" },
    { id: "search", label: "검색" },
    { id: "rename", label: "파일명 변경" },
    { id: "move", label: "폴더 분류" },
    { id: "log", label: "로그" },
  ] as const;

  let active = "search";
  let tauriMode = false;
  let status = "대기";
  let progressText = "";
  let progress: JobProgress = {
    processed: 0,
    total: 0,
    errors: 0,
    skipped: 0,
    startedAt: 0,
  };
  let stats: JobStats = {
    ok: 0,
    unknown: 0,
    conflict: 0,
    error: 0,
    skipped: 0,
  };
  let logs: string[] = [];
  let results: ResultRecord[] = [];
  let activeJobId: string | null = null;
  let activeJob: JobMode | null = null;
  let preset: Preset = { name: "", variables: [] };
  let presetPath: string | null = null;
  let presetStatus = "";
  let presetJobId: string | null = null;
  let presetJobMode: "load" | "save" | "import" | null = null;
  let presetImportTarget: { variableName: string; mode: "replace" | "append" } | null =
    null;
  let buildStatus = "";
  let buildCommonTags: string[] = [];
  let buildStats: Record<string, unknown> | null = null;
  let buildTarget: { name: string; mode: "replace" | "append" } | null = null;

  function appendLog(line: string) {
    logs = [line, ...logs].slice(0, 100);
  }

  function setPresetPath(path: string | null) {
    presetPath = path;
    if (typeof window === "undefined") {
      return;
    }
    const storageKey = "nai.template.path";
    if (!path) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    window.localStorage.setItem(storageKey, path);
    window.localStorage.removeItem("nai.preset.path");
  }

  function createJobId(mode: JobMode) {
    return `${mode}-${Date.now()}`;
  }

  function resetJob(mode: JobMode) {
    activeJob = mode;
    activeJobId = createJobId(mode);
    progress = {
      processed: 0,
      total: 0,
      errors: 0,
      skipped: 0,
      startedAt: Date.now(),
    };
    stats = { ok: 0, unknown: 0, conflict: 0, error: 0, skipped: 0 };
    results = [];
    updateProgressText();
  }

  function updateProgressText() {
    if (!activeJob) {
      progressText = "";
      return;
    }
    const eta = formatEta(progress);
    if (activeJob === "scan") {
      progressText = `스캔: ${progress.processed}/${progress.total} 오류 ${stats.error} 스킵 ${stats.skipped} ETA ${eta}`;
      return;
    }
    if (activeJob === "build_nais") {
      const text = `프리셋 만들기: ${progress.processed}/${progress.total} 오류 ${stats.error} ETA ${eta}`;
      progressText = text;
      buildStatus = text;
      return;
    }
    progressText = `진행: ${progress.processed}/${progress.total} OK ${stats.ok} UNKNOWN ${stats.unknown} CONFLICT ${stats.conflict} ERROR ${stats.error} ETA ${eta}`;
  }

  function addResult(status: ResultStatus, source?: string, target?: string, message?: string) {
    let text = status;
    if (source && target) {
      text = `${status} | ${source} -> ${target}`;
    } else if (source && message) {
      text = `${status} | ${source} | ${message}`;
    } else if (source) {
      text = `${status} | ${source}`;
    }
    const record: ResultRecord = {
      id: `${activeJobId ?? "job"}-${results.length}`,
      status,
      text,
      source,
      target,
      preview: target || source,
    };
    results = [record, ...results].slice(0, 2000);
  }

  function onMessage(message: IpcMessage) {
    if (message.type === "log") {
      appendLog(message.message ?? "로그 수신");
      return;
    }

    if (presetJobId && message.id === presetJobId) {
      if (message.type === "done") {
        const payload =
          message.payload && typeof message.payload === "object"
            ? (message.payload as Record<string, unknown>)
            : null;
        if (presetJobMode === "load" && payload?.preset) {
          preset = payload.preset as Preset;
          const path = typeof payload.path === "string" ? payload.path : presetPath;
          if (path) {
            setPresetPath(path);
          }
          presetStatus = "템플릿 불러오기 완료";
        } else if (presetJobMode === "save") {
          const path = typeof payload?.path === "string" ? payload.path : presetPath;
          if (path) {
            setPresetPath(path);
          }
          presetStatus = "템플릿 저장 완료";
        } else if (presetJobMode === "import" && payload?.values) {
          const values = coerceValues(payload.values);
          const target = presetImportTarget;
          if (target && values.length > 0) {
            applyBuildValues(target.variableName, values, target.mode);
            presetStatus = "프리셋 값 가져오기 완료";
          } else {
            presetStatus = "가져온 값이 없습니다.";
          }
        }
        presetJobId = null;
        presetJobMode = null;
        presetImportTarget = null;
      }
      if (message.type === "error") {
        presetStatus = `오류: ${message.message ?? "알 수 없음"}`;
        presetJobId = null;
        presetJobMode = null;
        presetImportTarget = null;
      }
      return;
    }

    if (message.id && activeJobId && message.id !== activeJobId) {
      return;
    }

    if (message.type === "progress") {
      progress.processed = Math.max(progress.processed, message.processed ?? 0);
      progress.total = message.total ?? progress.total;
      progress.errors = message.errors ?? progress.errors;
      progress.skipped = message.skipped ?? progress.skipped;
      if (activeJob === "scan") {
        stats.error = progress.errors;
        stats.skipped = progress.skipped;
      } else {
        stats.error = progress.errors;
      }
      updateProgressText();
      return;
    }

    if (message.type === "result") {
      const status = (message.status ?? "OK") as ResultStatus;
      addResult(status, message.source, message.target, message.message);
      if (status === "OK") stats.ok += 1;
      if (status === "UNKNOWN") stats.unknown += 1;
      if (status === "CONFLICT") stats.conflict += 1;
      if (status === "ERROR") stats.error += 1;
      updateProgressText();
      return;
    }

    if (message.type === "done") {
      if (activeJob === "build_nais") {
        status = "완료";
        buildStatus = "완료";
        progress.processed = Math.max(progress.processed, message.processed ?? 0);
        updateProgressText();

        const payload =
          message.payload && typeof message.payload === "object"
            ? (message.payload as Record<string, unknown>)
            : null;
        if (payload) {
          const rawName = payload.variable_name;
          const variableName =
            buildTarget?.name ||
            (typeof rawName === "string" ? rawName.trim() : "");
          const values = coerceValues(payload.values);
          if (variableName) {
            applyBuildValues(variableName, values, buildTarget?.mode ?? "replace");
          }
          buildCommonTags = Array.isArray(payload.common_tags)
            ? payload.common_tags.map((tag) => String(tag))
            : [];
        }

        buildStats =
          message.stats && typeof message.stats === "object"
            ? message.stats
            : null;
        return;
      }

      status = "완료";
      progress.processed = Math.max(progress.processed, message.processed ?? 0);
      stats.error = message.errors ?? stats.error;
      stats.skipped = message.skipped ?? stats.skipped;
      updateProgressText();
      return;
    }

    if (message.type === "error") {
      status = `오류: ${message.message ?? "알 수 없음"}`;
      appendLog(status);
      if (activeJob === "build_nais") {
        buildStatus = status;
      }
    }
  }

  async function runJob(mode: JobMode, payload: Record<string, unknown>) {
    if (!tauriMode) {
      status = "브라우저 모드에서는 IPC를 실행할 수 없습니다.";
      appendLog(status);
      return;
    }
    resetJob(mode);
    status = "요청 전송 중...";
    const request: IpcRunRequest = {
      id: activeJobId!,
      type: "run",
      op: mode,
      payload,
    };
    try {
      await runSidecarJob(request);
      status = "작업 시작";
    } catch (error) {
      status = `오류: ${String(error)}`;
      appendLog(status);
      if (mode === "build_nais") {
        buildStatus = status;
      }
    }
  }

  function runSearch(payload: { folder: string; tags: string; includeNegative: boolean }) {
    runJob("search", {
      folder: payload.folder,
      tags: payload.tags,
      include_negative: payload.includeNegative,
      progress_step: 200,
    });
  }

  function runScan(payload: {
    folder: string;
    includeNegative: boolean;
    incremental: boolean;
  }) {
    runJob("scan", {
      folder: payload.folder,
      include_negative: payload.includeNegative,
      incremental: payload.incremental,
      progress_step: 200,
      commit_step: 200,
    });
  }

  function runBuild(payload: {
    folder: string;
    includeNegative: boolean;
    targetName: string;
    mode: "replace" | "append";
  }) {
    if (!tauriMode) {
      buildStatus = "브라우저 모드에서는 실행할 수 없습니다.";
      appendLog(buildStatus);
      return;
    }
    if (!payload.folder.trim()) {
      buildStatus = "폴더를 입력하세요.";
      return;
    }
    if (!payload.targetName.trim()) {
      buildStatus = "변수 이름을 선택하거나 입력하세요.";
      return;
    }
    buildTarget = { name: payload.targetName.trim(), mode: payload.mode };
    buildStatus = "요청 전송 중...";
    buildCommonTags = [];
    buildStats = null;
    runJob("build_nais", {
      folder: payload.folder,
      include_negative: payload.includeNegative,
      progress_step: 200,
    });
  }

  function updatePreset(next: Preset) {
    preset = { ...next };
  }

  async function runPresetLoad(path: string) {
    if (!tauriMode) {
      presetStatus = "브라우저 모드에서는 실행할 수 없습니다.";
      appendLog(presetStatus);
      return;
    }
    presetStatus = "템플릿 불러오는 중...";
    presetJobMode = "load";
    presetJobId = `preset-load-${Date.now()}`;
    try {
      await runSidecarJob({
        id: presetJobId,
        type: "run",
        op: "preset_load",
        payload: { path },
      });
    } catch (error) {
      presetStatus = `오류: ${String(error)}`;
      appendLog(presetStatus);
      presetJobId = null;
      presetJobMode = null;
    }
  }

  async function runPresetSave(path: string) {
    if (!tauriMode) {
      presetStatus = "브라우저 모드에서는 실행할 수 없습니다.";
      appendLog(presetStatus);
      return;
    }
    presetStatus = "템플릿 저장 중...";
    presetJobMode = "save";
    presetJobId = `preset-save-${Date.now()}`;
    try {
      await runSidecarJob({
        id: presetJobId,
        type: "run",
        op: "preset_save",
        payload: { path, preset },
      });
    } catch (error) {
      presetStatus = `오류: ${String(error)}`;
      appendLog(presetStatus);
      presetJobId = null;
      presetJobMode = null;
    }
  }

  async function runPresetImport(
    path: string,
    mode: "replace" | "append",
    variableName: string
  ) {
    if (!tauriMode) {
      presetStatus = "브라우저 모드에서는 실행할 수 없습니다.";
      appendLog(presetStatus);
      return;
    }
    presetStatus = "프리셋 값 가져오는 중...";
    presetJobMode = "import";
    presetJobId = `preset-import-${Date.now()}`;
    presetImportTarget = { variableName, mode };
    try {
      await runSidecarJob({
        id: presetJobId,
        type: "run",
        op: "preset_import",
        payload: { path },
      });
    } catch (error) {
      presetStatus = `오류: ${String(error)}`;
      appendLog(presetStatus);
      presetJobId = null;
      presetJobMode = null;
      presetImportTarget = null;
    }
  }

  function coerceValues(rawValues: unknown): PresetValue[] {
    if (!Array.isArray(rawValues)) {
      return [];
    }
    const values: PresetValue[] = [];
    for (const raw of rawValues) {
      if (!raw || typeof raw !== "object") {
        continue;
      }
      const name = String((raw as Record<string, unknown>).name ?? "").trim();
      if (!name) {
        continue;
      }
      const tagList = (raw as Record<string, unknown>).tags;
      const tags = Array.isArray(tagList)
        ? normalizeTags(tagList.map((tag) => String(tag)))
        : [];
      values.push({ name, tags });
    }
    return values;
  }

  function ensureUniqueValueName(name: string, existing: Set<string>): string {
    let candidate = name;
    let idx = 2;
    while (existing.has(candidate)) {
      candidate = `${name}_${idx}`;
      idx += 1;
    }
    existing.add(candidate);
    return candidate;
  }

  function applyBuildValues(
    variableName: string,
    incoming: PresetValue[],
    mode: "replace" | "append"
  ) {
    const variables = [...preset.variables];
    const index = variables.findIndex((variable) => variable.name === variableName);
    if (index === -1) {
      variables.push({ name: variableName, values: incoming });
      preset = { ...preset, variables };
      return;
    }

    if (mode === "replace") {
      variables[index] = { ...variables[index], values: incoming };
      preset = { ...preset, variables };
      return;
    }

    const existingNames = new Set(variables[index].values.map((value) => value.name));
    const merged = [
      ...variables[index].values,
      ...incoming.map((value) => ({
        ...value,
        name: ensureUniqueValueName(value.name, existingNames),
      })),
    ];
    variables[index] = { ...variables[index], values: merged };
    preset = { ...preset, variables };
  }

  onMount(async () => {
    tauriMode = isTauri();
    status = tauriMode ? "대기" : "브라우저 모드";
    try {
      await connectSidecar(onMessage);
      appendLog("IPC 연결 준비 완료");
      if (typeof window !== "undefined") {
        const stored =
          window.localStorage.getItem("nai.template.path") ??
          window.localStorage.getItem("nai.preset.path");
        if (stored) {
          setPresetPath(stored);
          runPresetLoad(stored);
        }
      }
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
        <button class:active={active === tab.id} on:click={() => (active = tab.id)}>
          {tab.label}
        </button>
      {/each}
    </nav>
  </aside>

  <main class="main">
    {#if active === "editor"}
      <EditorView
        {preset}
        presetPath={presetPath}
        presetStatus={presetStatus}
        onChange={updatePreset}
        onBuild={runBuild}
        onPresetLoad={runPresetLoad}
        onPresetSave={runPresetSave}
        onPresetClear={() => {
          setPresetPath(null);
          presetStatus = "템플릿 자동 불러오기 경로를 초기화했습니다.";
        }}
        onPresetImport={runPresetImport}
        {buildStatus}
        buildStats={buildStats}
        buildCommonTags={buildCommonTags}
      />
    {:else if active === "search"}
      <SearchView
        status={status}
        {progressText}
        onSearch={runSearch}
        onScan={runScan}
        disabled={!tauriMode}
      />
      <ResultPanel records={results} title="검색 결과" />
    {:else if active === "log"}
      <LogPanel {logs} />
    {:else}
      <section class="panel">
        <div class="section-title">
          <h2>{active === "rename" ? "파일명 변경" : "폴더 분류"}</h2>
          <span class="badge">준비 중</span>
        </div>
        <p>이 탭은 다음 단계에서 연결합니다.</p>
      </section>
      <ResultPanel records={results} />
    {/if}
  </main>
</div>
