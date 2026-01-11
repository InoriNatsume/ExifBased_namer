<script lang="ts">
  import type { Preset } from "../../lib/preset";
  import { pickFile, saveFile } from "../../lib/dialog";

  export let preset: Preset;
  export let lastPath: string | null = null;
  export let status = "";
  export let onLoad: (path: string) => void;
  export let onSave: (path: string) => void;
  export let onClear: () => void;

  async function loadPreset() {
    const path = await pickFile(["json"]);
    if (!path) {
      return;
    }
    onLoad(path);
  }

  async function savePreset() {
    const defaultName = `${preset.name || "template"}.json`;
    const path = await saveFile(defaultName, ["json"]);
    if (!path) {
      return;
    }
    onSave(path);
  }
</script>

<div class="template-actions">
  <div class="row compact">
    <button class="ghost" on:click={loadPreset}>템플릿 불러오기</button>
    <button class="ghost" on:click={savePreset}>템플릿 저장</button>
    <button class="ghost" on:click={onClear} disabled={!lastPath}>
      자동 경로 초기화
    </button>
    {#if status}
      <span class="muted">{status}</span>
    {/if}
  </div>
  <div class="muted small">
    {#if lastPath}
      템플릿 자동 불러오기: {lastPath}
    {:else}
      템플릿 자동 불러오기 경로가 없습니다.
    {/if}
  </div>
</div>
