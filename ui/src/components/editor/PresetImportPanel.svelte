<script lang="ts">
  import { pickFile } from "../../lib/dialog";

  export type ImportMode = "replace" | "append";

  export let variableName: string | null = null;
  export let onImport: (path: string, mode: ImportMode) => void;

  let mode: ImportMode = "append";

  async function importPreset() {
    if (!variableName) {
      alert("먼저 변수를 선택하세요.");
      return;
    }
    const path = await pickFile(["json"]);
    if (!path) {
      return;
    }
    onImport(path, mode);
  }
</script>

<div class="panel inner">
  <div class="section-title small">
    <h3>SDSTUDIO/NAIS 템플릿 불러오기</h3>
  </div>
  <div class="muted">대상 변수: {variableName ?? "선택되지 않음"}</div>
  <div class="toggle-row">
    <label>
      <input type="radio" bind:group={mode} value="replace" />
      덮어쓰기
    </label>
    <label>
      <input type="radio" bind:group={mode} value="append" />
      기존 값에 추가
    </label>
  </div>
  <div class="row">
    <button class="primary" on:click={importPreset} disabled={!variableName}>
      템플릿 불러오기
    </button>
  </div>
  <div class="muted">
    프리셋은 변수 1개 단위입니다. 불러온 뒤 태그 편집의 공통 태그 제외로 공통 태그
    표시/제거가 가능합니다.
  </div>
</div>
