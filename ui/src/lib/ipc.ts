import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/core";
import type { IpcCancelRequest, IpcMessage, IpcRunRequest } from "./types";

const IPC_VERSION = 1;

declare global {
  interface Window {
    __TAURI_IPC__?: unknown;
    __TAURI__?: unknown;
    __TAURI_INTERNALS__?: unknown;
  }
}

export function isTauri(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return Boolean(
    (window as Window).__TAURI_IPC__ ||
      (window as Window).__TAURI__ ||
      (window as Window).__TAURI_INTERNALS__
  );
}

export async function connectSidecar(
  onMessage: (message: IpcMessage) => void
): Promise<() => void> {
  if (!isTauri()) {
    onMessage({
      type: "log",
      message: "브라우저 모드: IPC는 Tauri에서만 동작합니다.",
    });
    return () => undefined;
  }
  const unlisten = await listen<string>("sidecar-message", (event) => {
    try {
      const parsed = JSON.parse(event.payload) as IpcMessage;
      onMessage(parsed);
    } catch (error) {
      onMessage({ type: "log", message: String(error) });
    }
  });
  await listen<string>("sidecar-log", (event) => {
    onMessage({ type: "log", message: event.payload });
  });
  return unlisten;
}

export async function runSidecarJob(request: IpcRunRequest): Promise<void> {
  if (!isTauri()) {
    throw new Error("브라우저 모드에서는 IPC를 실행할 수 없습니다.");
  }
  const payload = { version: IPC_VERSION, ...request };
  await invoke("run_sidecar_job", {
    message: JSON.stringify(payload),
  });
}

export async function cancelSidecarJob(request: IpcCancelRequest): Promise<void> {
  if (!isTauri()) {
    throw new Error("브라우저 모드에서는 IPC를 실행할 수 없습니다.");
  }
  const payload = { version: IPC_VERSION, ...request };
  await invoke("run_sidecar_job", {
    message: JSON.stringify(payload),
  });
}
