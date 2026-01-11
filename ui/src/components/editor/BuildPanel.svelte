<script lang="ts">
  import type { PresetVariable } from "../../lib/preset";
  import { pickFolder } from "../../lib/dialog";

  export type BuildMode = "replace" | "append";

  export let variables: PresetVariable[] = [];
  export let onBuild: (payload: {
    folder: string;
    includeNegative: boolean;
    targetName: string;
    mode: BuildMode;
  }) => void;
  export let buildStatus = "";
  export let buildStats: Record<string, unknown> | null = null;
  export let buildCommonTags: string[] = [];

  let buildFolder = "";
  let buildIncludeNegative = false;
  let buildMode: BuildMode = "replace";
  let buildTarget = "__new__";
  let buildNewName = "";

  async function selectBuildFolder() {
    const selected = await pickFolder();
    if (selected) {
      buildFolder = selected;
      if (buildTarget === "__new__" && !buildNewName.trim()) {
        const parts = selected.split(/[\\/]+/).filter(Boolean);
        buildNewName = parts[parts.length - 1] ?? "";
      }
    }
  }

  function runBuild() {
    const targetName =
      buildTarget === "__new__" ? buildNewName.trim() : buildTarget;
    if (!buildFolder.trim()) {
      alert("폴더를 입력하세요.");
      return;
    }
    if (!targetName) {
      alert("적용할 변수 이름을 입력하세요.");
      return;
    }
    onBuild({
      folder: buildFolder,
      includeNegative: buildIncludeNegative,
      targetName,
      mode: buildMode,
    });
  }

  function readNumberStat(stats: Record<string, unknown> | null, key: string): number {
    if (!stats) {
      return 0;
    }
    const value = stats[key];
    return typeof value === "number" ? value : 0;
  }
</script>

<div class="panel inner">
  <div class="section-title small">
    <h3>이미지들로부터 프리셋 만들기</h3>
    <span class="badge">폴더 분석</span>
  </div>
  <div class="input-row">
    <input bind:value={buildFolder} placeholder="이미지 폴더 경로" />
    <button class="ghost" on:click={selectBuildFolder}>찾기</button>
  </div>
  <div class="toggle-row">
    <label>
      <input type="checkbox" bind:checked={buildIncludeNegative} /> 네거티브 태그 포함
    </label>
  </div>
  <div class="field">
    <div class="field-header">
      <span>적용 대상 변수</span>
    </div>
    <select bind:value={buildTarget}>
      <option value="__new__">새 변수 생성</option>
      {#each variables as variable}
        <option value={variable.name}>{variable.name}</option>
      {/each}
    </select>
    {#if buildTarget === "__new__"}
      <input bind:value={buildNewName} placeholder="새 변수 이름" />
    {/if}
  </div>
  <div class="toggle-row">
    <label>
      <input type="radio" bind:group={buildMode} value="replace" />
      덮어쓰기
    </label>
    <label>
      <input type="radio" bind:group={buildMode} value="append" />
      기존 값에 추가
    </label>
  </div>
  <div class="row">
    <button class="primary" on:click={runBuild}>프리셋 만들기</button>
    {#if buildStatus}
      <span class="muted">{buildStatus}</span>
    {/if}
  </div>
  {#if buildStats}
    <div class="muted">
      이미지 {readNumberStat(buildStats, "total")}장 · 공통 태그
      {readNumberStat(buildStats, "common_count")}개 · 고유 태그 없음
      {readNumberStat(buildStats, "empty_unique")}개
    </div>
  {/if}
  {#if buildCommonTags.length > 0}
    <div class="field">
      <div class="field-header">
        <span>공통 태그</span>
      </div>
      <textarea readonly rows="4">{buildCommonTags.join(", ")}</textarea>
    </div>
  {/if}
</div>
