<script lang="ts">
  import { onMount } from "svelte";
  import { get } from "svelte/store";
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
  import { jobStore, logStore, resultStore, templateStore } from "./lib/stores";
  import EditorView from "./components/EditorView.svelte";
  import SearchView from "./components/SearchView.svelte";
  import RenameView from "./components/RenameView.svelte";
  import MoveView from "./components/MoveView.svelte";
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
  let activeJobId: string | null = null;
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
    logStore.update((items) => [line, ...items].slice(0, 100));
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
    activeJobId = createJobId(mode);
    const progress: JobProgress = {
      processed: 0,
      total: 0,
      errors: 0,
      skipped: 0,
      startedAt: Date.now(),
    };
    const stats: JobStats = {
      ok: 0,
      unknown: 0,
      conflict: 0,
      error: 0,
      skipped: 0,
    };
    jobStore.set({
      activeJob: mode,
      status: "대기",
      progressText: "",
      progress,
      stats,
    });
    resultStore.set([]);
    updateProgressText();
  }

  function setJobStatus(text: string) {
    jobStore.update((state) => ({ ...state, status: text }));
  }

  function updateProgressText() {
    const state = get(jobStore);
    if (!state.activeJob) {
      jobStore.update((current) => ({ ...current, progressText: "" }));
      return;
    }
    const eta = formatEta(state.progress);
    if (state.activeJob === "scan") {
      jobStore.update((current) => ({
        ...current,
        progressText: `스캔: ${state.progress.processed}/${state.progress.total} 오류 ${state.stats.error} 스킵 ${state.stats.skipped} ETA ${eta}`,
      }));
      return;
    }
    if (state.activeJob === "build_nais") {
      const text = `프리셋 만들기: ${state.progress.processed}/${state.progress.total} 오류 ${state.stats.error} ETA ${eta}`;
      jobStore.update((current) => ({ ...current, progressText: text }));
      buildStatus = text;
      return;
    }
    jobStore.update((current) => ({
      ...current,
      progressText: `진행: ${state.progress.processed}/${state.progress.total} OK ${state.stats.ok} UNKNOWN ${state.stats.unknown} CONFLICT ${state.stats.conflict} ERROR ${state.stats.error} ETA ${eta}`,
    }));
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
    resultStore.update((items) => {
      const record: ResultRecord = {
        id: `${activeJobId ?? "job"}-${items.length}`,
        status,
        text,
        source,
        target,
        preview: target || source,
      };
      return [record, ...items].slice(0, 2000);
    });
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
          templateStore.set(payload.preset as Preset);
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
      jobStore.update((state) => {
        const progress = {
          ...state.progress,
          processed: Math.max(state.progress.processed, message.processed ?? 0),
          total: message.total ?? state.progress.total,
          errors: message.errors ?? state.progress.errors,
          skipped: message.skipped ?? state.progress.skipped,
        };
        const stats = { ...state.stats };
        if (state.activeJob === "scan") {
          stats.error = progress.errors;
          stats.skipped = progress.skipped;
        } else {
          stats.error = progress.errors;
        }
        return { ...state, progress, stats };
      });
      updateProgressText();
      return;
    }

    if (message.type === "result") {
      const resultStatus = (message.status ?? "OK") as ResultStatus;
      addResult(resultStatus, message.source, message.target, message.message);
      jobStore.update((state) => {
        const stats = { ...state.stats };
        if (resultStatus === "OK") stats.ok += 1;
        if (resultStatus === "UNKNOWN") stats.unknown += 1;
        if (resultStatus === "CONFLICT") stats.conflict += 1;
        if (resultStatus === "ERROR") stats.error += 1;
        return { ...state, stats };
      });
      updateProgressText();
      return;
    }

    if (message.type === "done") {
      if (get(jobStore).activeJob === "build_nais") {
        setJobStatus("완료");
        buildStatus = "완료";
        jobStore.update((state) => ({
          ...state,
          progress: {
            ...state.progress,
            processed: Math.max(state.progress.processed, message.processed ?? 0),
          },
        }));
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

      setJobStatus("완료");
      jobStore.update((state) => ({
        ...state,
        progress: {
          ...state.progress,
          processed: Math.max(state.progress.processed, message.processed ?? 0),
        },
        stats: {
          ...state.stats,
          error: message.errors ?? state.stats.error,
          skipped: message.skipped ?? state.stats.skipped,
        },
      }));
      updateProgressText();
      return;
    }

    if (message.type === "error") {
      const text = `오류: ${message.message ?? "알 수 없음"}`;
      setJobStatus(text);
      appendLog(text);
      if (get(jobStore).activeJob === "build_nais") {
        buildStatus = text;
      }
    }
  }

  async function runJob(mode: JobMode, payload: Record<string, unknown>) {
    if (!tauriMode) {
      setJobStatus("브라우저 모드에서는 IPC를 실행할 수 없습니다.");
      appendLog("브라우저 모드에서는 IPC를 실행할 수 없습니다.");
      return;
    }
    resetJob(mode);
    setJobStatus("요청 전송 중...");
    const request: IpcRunRequest = {
      id: activeJobId!,
      type: "run",
      op: mode,
      payload,
    };
    try {
      await runSidecarJob(request);
      setJobStatus("작업 시작");
    } catch (error) {
      const text = `오류: ${String(error)}`;
      setJobStatus(text);
      appendLog(text);
      if (mode === "build_nais") {
        buildStatus = text;
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

  function runRename(payload: {
    folder: string;
    order: string[];
    template: string;
    prefixMode: boolean;
    dryRun: boolean;
    includeNegative: boolean;
  }) {
    const template = get(templateStore);
    if (template.variables.length === 0) {
      setJobStatus("템플릿에 변수가 없습니다.");
      appendLog("템플릿에 변수가 없습니다.");
      return;
    }
    runJob("rename", {
      folder: payload.folder,
      order: payload.order,
      template: payload.template,
      prefix_mode: payload.prefixMode,
      dry_run: payload.dryRun,
      include_negative: payload.includeNegative,
      progress_step: 200,
      variables: template.variables,
    });
  }

  function runMove(payload: {
    folder: string;
    targetRoot: string;
    variableName: string;
    template: string;
    dryRun: boolean;
    includeNegative: boolean;
  }) {
    const template = get(templateStore);
    if (template.variables.length === 0) {
      setJobStatus("템플릿에 변수가 없습니다.");
      appendLog("템플릿에 변수가 없습니다.");
      return;
    }
    runJob("move", {
      folder: payload.folder,
      target_root: payload.targetRoot,
      variable_name: payload.variableName,
      template: payload.template,
      dry_run: payload.dryRun,
      include_negative: payload.includeNegative,
      progress_step: 200,
      variables: template.variables,
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
    templateStore.set({ ...next });
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
        payload: { path, preset: get(templateStore) },
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
    const template = get(templateStore);
    const variables = [...template.variables];
    const index = variables.findIndex((variable) => variable.name === variableName);
    if (index === -1) {
      variables.push({ name: variableName, values: incoming });
      templateStore.set({ ...template, variables });
      return;
    }

    if (mode === "replace") {
      variables[index] = { ...variables[index], values: incoming };
      templateStore.set({ ...template, variables });
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
    templateStore.set({ ...template, variables });
  }

  onMount(async () => {
    tauriMode = isTauri();
    setJobStatus(tauriMode ? "대기" : "브라우저 모드");
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
      setJobStatus("IPC 연결 실패");
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
        preset={$templateStore}
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
        status={$jobStore.status}
        progressText={$jobStore.progressText}
        processed={$jobStore.progress.processed}
        total={$jobStore.progress.total}
        onSearch={runSearch}
        onScan={runScan}
        disabled={!tauriMode}
      />
      <ResultPanel records={$resultStore} title="검색 결과" />
    {:else if active === "rename"}
      <RenameView
        variables={$templateStore.variables}
        status={$jobStore.status}
        progressText={$jobStore.progressText}
        processed={$jobStore.progress.processed}
        total={$jobStore.progress.total}
        onRun={runRename}
        disabled={!tauriMode}
      />
      <ResultPanel records={$resultStore} title="파일명 변경 결과" />
    {:else if active === "move"}
      <MoveView
        variables={$templateStore.variables}
        status={$jobStore.status}
        progressText={$jobStore.progressText}
        processed={$jobStore.progress.processed}
        total={$jobStore.progress.total}
        onRun={runMove}
        disabled={!tauriMode}
      />
      <ResultPanel records={$resultStore} title="폴더 분류 결과" />
    {:else if active === "log"}
      <LogPanel logs={$logStore} />
    {/if}
  </main>
</div>
