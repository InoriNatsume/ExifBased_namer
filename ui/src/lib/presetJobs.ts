import type { IpcMessage, IpcRunRequest } from "./types";
import type { Preset, PresetValue } from "./preset";

type PresetJobMode = "load" | "save" | "import";
type ImportTarget = { variableName: string; mode: "replace" | "append" };

type PresetJobDeps = {
  isTauri: () => boolean;
  getPresetPath: () => string | null;
  setPresetPath: (path: string | null) => void;
  setStatus: (text: string) => void;
  appendLog: (text: string) => void;
  setTemplate: (preset: Preset) => void;
  getTemplate: () => Preset;
  coerceValues: (rawValues: unknown) => PresetValue[];
  applyBuildValues: (
    variableName: string,
    incoming: PresetValue[],
    mode: "replace" | "append"
  ) => void;
  runSidecarJob: (request: IpcRunRequest) => Promise<void>;
};

export function createPresetJobManager(deps: PresetJobDeps) {
  let jobId: string | null = null;
  let jobMode: PresetJobMode | null = null;
  let importTarget: ImportTarget | null = null;

  function reset() {
    jobId = null;
    jobMode = null;
    importTarget = null;
  }

  function handleMessage(message: IpcMessage): boolean {
    if (!jobId || message.id !== jobId) {
      return false;
    }

    if (message.type === "done") {
      const payload =
        message.payload && typeof message.payload === "object"
          ? (message.payload as Record<string, unknown>)
          : null;
      if (jobMode === "load") {
        if (payload?.preset) {
          deps.setTemplate(payload.preset as Preset);
          const path = typeof payload.path === "string" ? payload.path : deps.getPresetPath();
          if (path) {
            deps.setPresetPath(path);
          }
          deps.setStatus("템플릿 파일 불러오기 완료");
        } else {
          deps.setStatus("템플릿 데이터를 찾을 수 없습니다.");
        }
      } else if (jobMode === "save") {
        const path = typeof payload?.path === "string" ? payload.path : deps.getPresetPath();
        if (path) {
          deps.setPresetPath(path);
        }
        deps.setStatus("템플릿 파일 저장 완료");
      } else if (jobMode === "import") {
        if (payload?.values) {
          const values = deps.coerceValues(payload.values);
          const target = importTarget;
          if (target && values.length > 0) {
            deps.applyBuildValues(target.variableName, values, target.mode);
            deps.setStatus("프리셋 불러오기 완료");
          } else {
            deps.setStatus("가져온 값이 없습니다.");
          }
        } else {
          deps.setStatus("프리셋 데이터를 찾을 수 없습니다.");
        }
      }
      reset();
      return true;
    }

    if (message.type === "error") {
      const text = `오류: ${message.message ?? "알 수 없음"}`;
      deps.setStatus(text);
      deps.appendLog(text);
      reset();
      return true;
    }

    return true;
  }

  async function runPresetLoad(path: string) {
    if (!deps.isTauri()) {
      const text = "브라우저 모드에서는 실행할 수 없습니다.";
      deps.setStatus(text);
      deps.appendLog(text);
      return;
    }
    deps.setStatus("템플릿 파일 불러오는 중...");
    jobMode = "load";
    jobId = `preset-load-${Date.now()}`;
    try {
      await deps.runSidecarJob({
        id: jobId,
        type: "run",
        op: "preset_load",
        payload: { path },
      });
    } catch (error) {
      const text = `오류: ${String(error)}`;
      deps.setStatus(text);
      deps.appendLog(text);
      reset();
    }
  }

  async function runPresetSave(path: string) {
    if (!deps.isTauri()) {
      const text = "브라우저 모드에서는 실행할 수 없습니다.";
      deps.setStatus(text);
      deps.appendLog(text);
      return;
    }
    deps.setStatus("템플릿 파일 저장 중...");
    jobMode = "save";
    jobId = `preset-save-${Date.now()}`;
    try {
      await deps.runSidecarJob({
        id: jobId,
        type: "run",
        op: "preset_save",
        payload: { path, preset: deps.getTemplate() },
      });
    } catch (error) {
      const text = `오류: ${String(error)}`;
      deps.setStatus(text);
      deps.appendLog(text);
      reset();
    }
  }

  async function runPresetImport(
    path: string,
    mode: "replace" | "append",
    variableName: string
  ) {
    if (!deps.isTauri()) {
      const text = "브라우저 모드에서는 실행할 수 없습니다.";
      deps.setStatus(text);
      deps.appendLog(text);
      return;
    }
    deps.setStatus("프리셋 불러오는 중...");
    jobMode = "import";
    jobId = `preset-import-${Date.now()}`;
    importTarget = { variableName, mode };
    try {
      await deps.runSidecarJob({
        id: jobId,
        type: "run",
        op: "preset_import",
        payload: { path },
      });
    } catch (error) {
      const text = `오류: ${String(error)}`;
      deps.setStatus(text);
      deps.appendLog(text);
      reset();
    }
  }

  return {
    handleMessage,
    runPresetLoad,
    runPresetSave,
    runPresetImport,
  };
}
