<script lang="ts">
  import { onMount } from "svelte";
  import { get } from "svelte/store";
  import {
    cancelSidecarJob,
    connectSidecar,
    isTauri,
    runSidecarJob,
  } from "./lib/ipc";
  import type { IpcMessage, IpcRunRequest } from "./lib/types";
  import {
    formatEta,
    type JobMode,
    type JobProgress,
    type JobStats,
    type ResultRecord,
    type ResultStatus,
  } from "./lib/models";
  import type { Preset, PresetValue } from "./lib/preset";
  import { createPresetJobManager } from "./lib/presetJobs";
  import type { PresetInfo, TemplateInfo } from "./lib/dbModels";
  import { createPresetDbManager } from "./lib/presetDbJobs";
  import { createTemplateDbManager } from "./lib/templateDbJobs";
  import { jobStore, logStore, resultStore, templateStore } from "./lib/stores";
  import { applyBuildValues, coerceValues } from "./lib/templateOps";
  import EditorView from "./components/EditorView.svelte";
  import SearchView from "./components/SearchView.svelte";
  import RenameView from "./components/RenameView.svelte";
  import MoveView from "./components/MoveView.svelte";
  import ResultPanel from "./components/ResultPanel.svelte";
  import LogPanel from "./components/LogPanel.svelte";
  import HelpView from "./components/HelpView.svelte";

  const tabs = [
    { id: "editor", label: "편집" },
    { id: "search", label: "검색" },
    { id: "rename", label: "파일명 변경" },
    { id: "move", label: "폴더 분류" },
    { id: "help", label: "안내" },
    { id: "log", label: "로그" },
  ] as const;

  let active = "search";
  let tauriMode = false;
  let activeJobId: string | null = null;
  let presetPath: string | null = null;
  let presetStatus = "";
  let templateDbStatus = "";
  let templateDbItems: TemplateInfo[] = [];
  let templateDbSelected: string | null = null;
  let presetDbStatus = "";
  let presetDbItems: PresetInfo[] = [];
  let resumeClearJobId: string | null = null;
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

  function setTemplateDbName(name: string | null) {
    templateDbSelected = name;
    if (typeof window === "undefined") {
      return;
    }
    const storageKey = "nai.template.db.name";
    if (!name) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    window.localStorage.setItem(storageKey, name);
  }

  const presetJobs = createPresetJobManager({
    isTauri: () => tauriMode,
    getPresetPath: () => presetPath,
    setPresetPath,
    setStatus: (text) => {
      presetStatus = text;
    },
    appendLog,
    setTemplate: (preset) => templateStore.set(preset),
    getTemplate: () => get(templateStore),
    coerceValues,
    applyBuildValues,
    runSidecarJob,
  });

  const templateDbJobs = createTemplateDbManager({
    isTauri: () => tauriMode,
    setStatus: (text) => {
      templateDbStatus = text;
    },
    appendLog,
    setTemplates: (items) => {
      templateDbItems = items;
    },
    setTemplate: (preset) => templateStore.set(preset),
    setSelectedName: setTemplateDbName,
    runSidecarJob,
  });

  const presetDbJobs = createPresetDbManager({
    isTauri: () => tauriMode,
    setStatus: (text) => {
      presetDbStatus = text;
    },
    appendLog,
    setPresets: (items) => {
      presetDbItems = items;
    },
    applyValues: (variableName, values, mode) => {
      applyBuildValues(variableName, values, mode);
    },
    runSidecarJob,
  });

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
    const skipText = state.stats.skipped ? ` SKIP ${state.stats.skipped}` : "";
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
      progressText: `진행: ${state.progress.processed}/${state.progress.total} OK ${state.stats.ok} UNKNOWN ${state.stats.unknown} CONFLICT ${state.stats.conflict} ERROR ${state.stats.error}${skipText} ETA ${eta}`,
    }));
  }

  function addResult(
    status: ResultStatus,
    source?: string,
    target?: string,
    message?: string,
    preview?: string
  ) {
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
        preview: preview || target || source,
      };
      return [record, ...items].slice(0, 2000);
    });
  }

  function onMessage(message: IpcMessage) {
    if (message.type === "log") {
      appendLog(message.message ?? "로그 수신");
      return;
    }

    if (templateDbJobs.handleMessage(message)) {
      return;
    }

    if (presetDbJobs.handleMessage(message)) {
      return;
    }

    if (presetJobs.handleMessage(message)) {
      return;
    }

    if (resumeClearJobId && message.id === resumeClearJobId) {
      if (message.type === "done") {
        const payload =
          message.payload && typeof message.payload === "object"
            ? (message.payload as Record<string, unknown>)
            : null;
        const path = typeof payload?.path === "string" ? payload.path : "";
        setJobStatus("재개 파일 삭제 완료");
        appendLog(path ? `재개 파일 삭제: ${path}` : "재개 파일 삭제 완료");
      }
      if (message.type === "error") {
        const text = `오류: ${message.message ?? "알 수 없음"}`;
        setJobStatus(text);
        appendLog(text);
      }
      resumeClearJobId = null;
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
          if (typeof message.skipped === "number") {
            stats.skipped = message.skipped;
          }
        }
        return { ...state, progress, stats };
      });
      updateProgressText();
      return;
    }

    if (message.type === "result") {
      const resultStatus = (message.status ?? "OK") as ResultStatus;
      addResult(
        resultStatus,
        message.source,
        message.target,
        message.message,
        message.preview
      );
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
      if (message.cancelled) {
        setJobStatus("중단됨");
        appendLog("작업 중단됨");
      }
      if (get(jobStore).activeJob === "build_nais") {
        if (!message.cancelled) {
          setJobStatus("완료");
          buildStatus = "완료";
        } else {
          buildStatus = "중단됨";
        }
        jobStore.update((state) => ({
          ...state,
          progress: {
            ...state.progress,
            processed: Math.max(state.progress.processed, message.processed ?? 0),
          },
        }));
        updateProgressText();
        activeJobId = null;

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

      if (!message.cancelled) {
        setJobStatus("완료");
      }
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
      activeJobId = null;
      return;
    }

    if (message.type === "error") {
      const text = `오류: ${message.message ?? "알 수 없음"}`;
      setJobStatus(text);
      appendLog(text);
      if (get(jobStore).activeJob === "build_nais") {
        buildStatus = text;
      }
      activeJobId = null;
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

  async function cancelActiveJob() {
    if (!tauriMode || !activeJobId) {
      return;
    }
    setJobStatus("중단 요청...");
    try {
      await cancelSidecarJob({ id: activeJobId, type: "cancel" });
      appendLog("중단 요청 전송");
    } catch (error) {
      const text = `오류: ${String(error)}`;
      setJobStatus(text);
      appendLog(text);
    }
  }

  async function clearResumeFile(kind: "rename" | "move", folder: string) {
    if (!tauriMode) {
      setJobStatus("브라우저 모드에서는 IPC를 실행할 수 없습니다.");
      appendLog("브라우저 모드에서는 IPC를 실행할 수 없습니다.");
      return;
    }
    if (!folder.trim()) {
      setJobStatus("폴더를 입력하세요.");
      return;
    }
    resumeClearJobId = `resume-clear-${kind}-${Date.now()}`;
    setJobStatus("재개 파일 삭제 중...");
    try {
      await runSidecarJob({
        id: resumeClearJobId,
        type: "run",
        op: "resume_clear",
        payload: { folder, kind },
      });
    } catch (error) {
      const text = `오류: ${String(error)}`;
      setJobStatus(text);
      appendLog(text);
      resumeClearJobId = null;
    }
  }

  function runSearch(payload: {
    folder: string;
    tags: string;
    includeNegative: boolean;
    thumbs: boolean;
  }) {
    runJob("search", {
      folder: payload.folder,
      tags: payload.tags,
      include_negative: payload.includeNegative,
      progress_step: 200,
      thumbs: payload.thumbs,
    });
  }

  function runScan(payload: {
    folder: string;
    includeNegative: boolean;
    incremental: boolean;
    thumbs: boolean;
  }) {
    runJob("scan", {
      folder: payload.folder,
      include_negative: payload.includeNegative,
      incremental: payload.incremental,
      progress_step: 200,
      commit_step: 200,
      thumbs: payload.thumbs,
    });
  }

  function runRename(payload: {
    folder: string;
    order: string[];
    template: string;
    prefixMode: boolean;
    dryRun: boolean;
    includeNegative: boolean;
    resumeMode: boolean;
    thumbs: boolean;
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
      resume_mode: payload.resumeMode,
      checkpoint_step: 200,
      thumbs: payload.thumbs,
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
    resumeMode: boolean;
    thumbs: boolean;
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
      resume_mode: payload.resumeMode,
      checkpoint_step: 200,
      thumbs: payload.thumbs,
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

  function refreshTemplateDb() {
    templateDbJobs.runList();
  }

  function loadTemplateDb(name: string) {
    templateDbJobs.runGet(name);
  }

  function saveTemplateDb() {
    templateDbJobs.runSave(get(templateStore));
  }

  function deleteTemplateDb(name: string) {
    if (templateDbSelected === name) {
      setTemplateDbName(null);
    }
    templateDbJobs.runDelete(name);
  }

  function refreshPresetDb(variableName: string | null) {
    if (!variableName) {
      presetDbItems = [];
      presetDbStatus = "변수를 선택하세요.";
      return;
    }
    presetDbJobs.runList(variableName);
  }

  function applyPresetDb(
    presetId: number,
    mode: "replace" | "append",
    variableName: string
  ) {
    presetDbJobs.runGet(presetId, variableName, mode);
  }

  function savePresetDb(payload: {
    name: string;
    sourceKind: string;
    variableName: string;
    values: PresetValue[];
  }) {
    presetDbJobs.runSave(payload);
  }

  function deletePresetDb(presetId: number) {
    presetDbJobs.runDelete(presetId);
  }

  onMount(async () => {
    tauriMode = isTauri();
    setJobStatus(tauriMode ? "대기" : "브라우저 모드");
    try {
      await connectSidecar(onMessage);
      appendLog("IPC 연결 준비 완료");
      if (tauriMode) {
        templateDbJobs.runList();
      }
      if (typeof window !== "undefined") {
        const storedDbName = window.localStorage.getItem("nai.template.db.name");
        if (storedDbName) {
          setTemplateDbName(storedDbName);
          if (tauriMode) {
            templateDbJobs.runGet(storedDbName);
          }
        } else {
          const stored =
            window.localStorage.getItem("nai.template.path") ??
            window.localStorage.getItem("nai.preset.path");
          if (stored) {
            setPresetPath(stored);
            presetJobs.runPresetLoad(stored);
          }
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
        templateDbItems={templateDbItems}
        templateDbSelected={templateDbSelected}
        templateDbStatus={templateDbStatus}
        onChange={updatePreset}
        onBuild={runBuild}
        onPresetLoad={presetJobs.runPresetLoad}
        onPresetSave={presetJobs.runPresetSave}
        onPresetClear={() => {
          setPresetPath(null);
          presetStatus = "템플릿 자동 불러오기 경로를 초기화했습니다.";
        }}
        onPresetImport={presetJobs.runPresetImport}
        onTemplateDbRefresh={refreshTemplateDb}
        onTemplateDbLoad={loadTemplateDb}
        onTemplateDbSave={saveTemplateDb}
        onTemplateDbDelete={deleteTemplateDb}
        presetDbItems={presetDbItems}
        presetDbStatus={presetDbStatus}
        onPresetDbRefresh={refreshPresetDb}
        onPresetDbApply={applyPresetDb}
        onPresetDbSave={savePresetDb}
        onPresetDbDelete={deletePresetDb}
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
        onCancel={activeJobId ? cancelActiveJob : null}
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
        onCancel={activeJobId ? cancelActiveJob : null}
        onClearResume={(folder) => clearResumeFile("rename", folder)}
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
        onCancel={activeJobId ? cancelActiveJob : null}
        onClearResume={(folder) => clearResumeFile("move", folder)}
        disabled={!tauriMode}
      />
      <ResultPanel records={$resultStore} title="폴더 분류 결과" />
    {:else if active === "help"}
      <HelpView />
    {:else if active === "log"}
      <LogPanel logs={$logStore} />
    {/if}
  </main>
</div>
