import type { IpcMessage, IpcRunRequest } from "./types";
import type { Preset } from "./preset";
import type { TemplateInfo } from "./dbModels";

type TemplateDbMode = "list" | "get" | "save" | "delete";

type TemplateDbDeps = {
  isTauri: () => boolean;
  setStatus: (text: string) => void;
  appendLog: (text: string) => void;
  setTemplates: (items: TemplateInfo[]) => void;
  setTemplate: (template: Preset) => void;
  setSelectedName: (name: string | null) => void;
  runSidecarJob: (request: IpcRunRequest) => Promise<void>;
};

export function createTemplateDbManager(deps: TemplateDbDeps) {
  let jobId: string | null = null;
  let mode: TemplateDbMode | null = null;
  let lastListRequested = false;

  function reset() {
    jobId = null;
    mode = null;
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
        const items = Array.isArray(payload?.templates)
          ? (payload?.templates as TemplateInfo[])
          : [];
        deps.setTemplates(items);
        deps.setStatus("템플릿 목록을 불러왔습니다.");
      } else if (mode === "get") {
        const templatePayload =
          payload && typeof payload.payload === "object"
            ? (payload.payload as Preset)
            : null;
        if (templatePayload) {
          deps.setTemplate(templatePayload);
          const name = typeof payload?.name === "string" ? payload.name : templatePayload.name;
          if (name) {
            deps.setSelectedName(name);
          }
          deps.setStatus("템플릿을 불러왔습니다.");
        } else {
          deps.setStatus("템플릿 데이터를 찾을 수 없습니다.");
        }
      } else if (mode === "save") {
        const name = typeof payload?.name === "string" ? payload.name : null;
        if (name) {
          deps.setSelectedName(name);
        }
        deps.setStatus("템플릿을 저장했습니다.");
        lastListRequested = true;
        void runList();
      } else if (mode === "delete") {
        deps.setStatus("템플릿을 삭제했습니다.");
        lastListRequested = true;
        void runList();
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

  async function runList() {
    if (!deps.isTauri()) {
      deps.setStatus("브라우저 모드에서는 사용할 수 없습니다.");
      deps.appendLog("브라우저 모드에서는 템플릿 DB를 사용할 수 없습니다.");
      return;
    }
    deps.setStatus("템플릿 목록을 불러오는 중...");
    jobId = `template-db-list-${Date.now()}`;
    mode = "list";
    try {
      await deps.runSidecarJob({
        id: jobId,
        type: "run",
        op: "template_db_list",
        payload: {},
      });
    } catch (error) {
      deps.setStatus(`오류: ${String(error)}`);
      deps.appendLog(`오류: ${String(error)}`);
      reset();
    }
  }

  async function runGet(name: string) {
    if (!deps.isTauri()) {
      deps.setStatus("브라우저 모드에서는 사용할 수 없습니다.");
      deps.appendLog("브라우저 모드에서는 템플릿 DB를 사용할 수 없습니다.");
      return;
    }
    if (!name.trim()) {
      deps.setStatus("템플릿 이름을 선택하세요.");
      return;
    }
    deps.setStatus("템플릿을 불러오는 중...");
    jobId = `template-db-get-${Date.now()}`;
    mode = "get";
    try {
      await deps.runSidecarJob({
        id: jobId,
        type: "run",
        op: "template_db_get",
        payload: { name },
      });
    } catch (error) {
      deps.setStatus(`오류: ${String(error)}`);
      deps.appendLog(`오류: ${String(error)}`);
      reset();
    }
  }

  async function runSave(template: Preset, overrideName?: string | null) {
    if (!deps.isTauri()) {
      deps.setStatus("브라우저 모드에서는 사용할 수 없습니다.");
      deps.appendLog("브라우저 모드에서는 템플릿 DB를 사용할 수 없습니다.");
      return;
    }
    const name = overrideName?.trim() || template.name?.trim();
    if (!name) {
      deps.setStatus("템플릿 이름을 입력하세요.");
      return;
    }
    deps.setStatus("템플릿을 저장하는 중...");
    jobId = `template-db-save-${Date.now()}`;
    mode = "save";
    try {
      await deps.runSidecarJob({
        id: jobId,
        type: "run",
        op: "template_db_save",
        payload: { name, template },
      });
    } catch (error) {
      deps.setStatus(`오류: ${String(error)}`);
      deps.appendLog(`오류: ${String(error)}`);
      reset();
    }
  }

  async function runDelete(name: string) {
    if (!deps.isTauri()) {
      deps.setStatus("브라우저 모드에서는 사용할 수 없습니다.");
      deps.appendLog("브라우저 모드에서는 템플릿 DB를 사용할 수 없습니다.");
      return;
    }
    if (!name.trim()) {
      deps.setStatus("삭제할 템플릿을 선택하세요.");
      return;
    }
    deps.setStatus("템플릿을 삭제하는 중...");
    jobId = `template-db-delete-${Date.now()}`;
    mode = "delete";
    try {
      await deps.runSidecarJob({
        id: jobId,
        type: "run",
        op: "template_db_delete",
        payload: { name },
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
    lastListRequested: () => lastListRequested,
  };
}
