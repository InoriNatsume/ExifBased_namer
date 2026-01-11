import { isTauri } from "./ipc";

export async function pickFolder(): Promise<string | null> {
  if (!isTauri()) {
    if (typeof window === "undefined") {
      return null;
    }
    const input = window.prompt("폴더 경로를 입력하세요.");
    return input?.trim() || null;
  }
  try {
    const dialog = await import("@tauri-apps/plugin-dialog");
    const result = await dialog.open({
      directory: true,
      multiple: false,
    });
    if (Array.isArray(result)) {
      return result[0] ?? null;
    }
    return result ?? null;
  } catch (error) {
    console.error(error);
    return null;
  }
}

export async function pickFile(extensions: string[] = ["json"]): Promise<string | null> {
  if (!isTauri()) {
    if (typeof window === "undefined") {
      return null;
    }
    const input = window.prompt("파일 경로를 입력하세요.");
    return input?.trim() || null;
  }
  try {
    const dialog = await import("@tauri-apps/plugin-dialog");
    const result = await dialog.open({
      multiple: false,
      filters: [
        {
          name: "JSON",
          extensions,
        },
      ],
    });
    if (Array.isArray(result)) {
      return result[0] ?? null;
    }
    return result ?? null;
  } catch (error) {
    console.error(error);
    return null;
  }
}

export async function saveFile(
  defaultName: string,
  extensions: string[] = ["json"]
): Promise<string | null> {
  if (!isTauri()) {
    if (typeof window === "undefined") {
      return null;
    }
    const input = window.prompt("저장할 파일 경로를 입력하세요.", defaultName);
    return input?.trim() || null;
  }
  try {
    const dialog = await import("@tauri-apps/plugin-dialog");
    const result = await dialog.save({
      defaultPath: defaultName,
      filters: [
        {
          name: "JSON",
          extensions,
        },
      ],
    });
    return result ?? null;
  } catch (error) {
    console.error(error);
    return null;
  }
}
