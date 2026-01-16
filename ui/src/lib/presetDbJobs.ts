import type { IpcMessage, IpcRunRequest } from "./types";
import type { PresetValue } from "./preset";
import type { PresetInfo } from "./dbModels";

type PresetDbMode = "list" | "get" | "save" | "delete";

type PresetDbDeps = {
  isTauri: () => boolean;
  setStatus: (text: string) => void;
  appendLog: (text: string) => void;
  setPresets: (items: PresetInfo[]) => void;
  applyValues: (variableName: string, values: PresetValue[], mode: "replace" | "append") => void;
  runSidecarJob: (request: IpcRunRequest) => Promise<void>;
};

type PendingApply = {
  variableName: string;
  mode: "replace" | "append";
};

type PendingList = {
  variableName?: string | null;
  sourceKind?: string | null;
};

export function createPresetDbManager(deps: PresetDbDeps) {
  let jobId: string | null = null;
  let mode: PresetDbMode | null = null;
  let pendingApply: PendingApply | null = null;
  let lastList: PendingList | null = null;

  function reset() {
    jobId = null;
    mode = null;
    pendingApply = null;
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
      if (mode === "list") {
        const items = Array.isArray(payload?.presets)
          ? (payload?.presets as PresetInfo[])
          : [];
        deps.setPresets(items);
        deps.setStatus("프리셋 목록을 불러왔습니다.");
      } else if (mode === "get") {
        const values = Array.isArray(payload?.payload && (payload.payload as Record<string, unknown>).values)
          ? ((payload?.payload as Record<string, unknown>).values as PresetValue[])
          : null;
        if (pendingApply && values) {
          deps.applyValues(pendingApply.variableName, values, pendingApply.mode);
          deps.setStatus("프리셋을 적용했습니다.");
        } else {
          deps.setStatus("프리셋 데이터를 찾을 수 없습니다.");
        }
      } else if (mode === "save") {
        deps.setStatus("프리셋을 저장했습니다.");
        if (lastList) {
          void runList(lastList.variableName ?? undefined, lastList.sourceKind ?? undefined);
        }
      } else if (mode === "delete") {
        deps.setStatus("프리셋을 삭제했습니다.");
        if (lastList) {
          void runList(lastList.variableName ?? undefined, lastList.sourceKind ?? undefined);
        }
      }
      reset();
      return true;
    }

    if (message.type === "error") {
      deps.setStatus(`오류: ${message.message ?? "알 수 없음"}`);
      reset();
      return true;
    }

    return true;
  }

  async function runList(variableName?: string | null, sourceKind?: string | null) {
    if (!deps.isTauri()) {
      deps.setStatus("브라우저 모드에서는 사용할 수 없습니다.");
      deps.appendLog("브라우저 모드에서는 프리셋 DB를 사용할 수 없습니다.");
      return;
    }
    jobId = `preset-db-list-${Date.now()}`;
    mode = "list";
    lastList = { variableName, sourceKind };
    deps.setStatus("프리셋 목록을 불러오는 중...");
    try {
      await deps.runSidecarJob({
        id: jobId,
        type: "run",
        op: "preset_db_list",
        payload: {
          variable_name: variableName ?? undefined,
          source_kind: sourceKind ?? undefined,
        },
      });
    } catch (error) {
      deps.setStatus(`오류: ${String(error)}`);
      deps.appendLog(`오류: ${String(error)}`);
      reset();
    }
  }

  async function runGet(presetId: number, variableName: string, modeValue: "replace" | "append") {
    if (!deps.isTauri()) {
      deps.setStatus("브라우저 모드에서는 사용할 수 없습니다.");
      deps.appendLog("브라우저 모드에서는 프리셋 DB를 사용할 수 없습니다.");
      return;
    }
    jobId = `preset-db-get-${Date.now()}`;
    mode = "get";
    pendingApply = { variableName, mode: modeValue };
    deps.setStatus("프리셋을 불러오는 중...");
    try {
      await deps.runSidecarJob({
        id: jobId,
        type: "run",
        op: "preset_db_get",
        payload: { id: presetId },
      });
    } catch (error) {
      deps.setStatus(`오류: ${String(error)}`);
      deps.appendLog(`오류: ${String(error)}`);
      reset();
    }
  }

  async function runSave(payload: {
    id?: number;
    name: string;
    sourceKind: string;
    variableName: string;
    values: PresetValue[];
  }) {
    if (!deps.isTauri()) {
      deps.setStatus("브라우저 모드에서는 사용할 수 없습니다.");
      deps.appendLog("브라우저 모드에서는 프리셋 DB를 사용할 수 없습니다.");
      return;
    }
    if (!payload.name.trim()) {
      deps.setStatus("프리셋 이름을 입력하세요.");
      return;
    }
    jobId = `preset-db-save-${Date.now()}`;
    mode = "save";
    lastList = { variableName: payload.variableName, sourceKind: payload.sourceKind };
    deps.setStatus("프리셋을 저장하는 중...");
    try {
      await deps.runSidecarJob({
        id: jobId,
        type: "run",
        op: "preset_db_save",
        payload: {
          id: payload.id,
          name: payload.name,
          source_kind: payload.sourceKind,
          variable_name: payload.variableName,
          preset: {
            name: payload.name,
            source_kind: payload.sourceKind,
            variable_name: payload.variableName,
            values: payload.values,
          },
        },
      });
    } catch (error) {
      deps.setStatus(`오류: ${String(error)}`);
      deps.appendLog(`오류: ${String(error)}`);
      reset();
    }
  }

  async function runDelete(presetId: number) {
    if (!deps.isTauri()) {
      deps.setStatus("브라우저 모드에서는 사용할 수 없습니다.");
      deps.appendLog("브라우저 모드에서는 프리셋 DB를 사용할 수 없습니다.");
      return;
    }
    jobId = `preset-db-delete-${Date.now()}`;
    mode = "delete";
    deps.setStatus("프리셋을 삭제하는 중...");
    try {
      await deps.runSidecarJob({
        id: jobId,
        type: "run",
        op: "preset_db_delete",
        payload: { id: presetId },
      });
    } catch (error) {
      deps.setStatus(`오류: ${String(error)}`);
      deps.appendLog(`오류: ${String(error)}`);
      reset();
    }
  }

  return {
    handleMessage,
    runList,
    runGet,
    runSave,
    runDelete,
  };
}
