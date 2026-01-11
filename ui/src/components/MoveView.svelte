<script lang="ts">
  import { pickFolder } from "../lib/dialog";
  import ProgressBar from "./ProgressBar.svelte";
  import type { PresetVariable } from "../lib/preset";

  export let variables: PresetVariable[] = [];
  export let status = "대기";
  export let progressText = "";
  export let processed = 0;
  export let total = 0;
  export let onRun: (payload: {
    folder: string;
    targetRoot: string;
    variableName: string;
    template: string;
    dryRun: boolean;
    includeNegative: boolean;
  }) => void;
  export let disabled = false;

  let folder = "";
  let targetRoot = "";
  let variableName = "";
  let template = "[value]";
  let dryRun = true;
  let includeNegative = false;
  let localStatus = "";

  $: displayStatus = localStatus || status;
  $: availableNames = variables.map((variable) => variable.name);
  $: if (!variableName && availableNames.length > 0) {
    variableName = availableNames[0];
  }

  async function selectFolder() {
    const selected = await pickFolder();
    if (selected) {
      folder = selected;
      localStatus = "";
    }
  }

  async function selectTargetRoot() {
    const selected = await pickFolder();
    if (selected) {
      targetRoot = selected;
      localStatus = "";
    }
  }

  function runMove() {
    if (!folder.trim()) {
      localStatus = "작업 폴더를 입력하세요.";
      return;
    }
    if (!targetRoot.trim()) {
      localStatus = "대상 폴더를 입력하세요.";
      return;
    }
    if (!variableName.trim()) {
      localStatus = "변수를 선택하세요.";
      return;
    }
    localStatus = "";
    onRun({
      folder,
      targetRoot,
      variableName,
      template: template.trim() || "[value]",
      dryRun,
      includeNegative,
    });
  }
</script>

<section class="panel">
  <div class="section-title">
    <h2>폴더 분류</h2>
    <span class="badge">IPC 준비</span>
  </div>
  <div class="input-row">
    <input bind:value={folder} placeholder="작업 폴더 경로" />
    <div class="button-row">
      <button class="ghost" on:click={selectFolder} disabled={disabled}>찾기</button>
    </div>
  </div>
  <div class="input-row">
    <input bind:value={targetRoot} placeholder="대상 폴더 경로" />
    <div class="button-row">
      <button class="ghost" on:click={selectTargetRoot} disabled={disabled}>찾기</button>
      <button class="primary" on:click={runMove} disabled={disabled}>실행</button>
    </div>
  </div>
  <div class="input-row">
    <select bind:value={variableName} disabled={availableNames.length === 0}>
      {#each availableNames as name}
        <option value={name}>{name}</option>
      {/each}
    </select>
    <div class="muted">분류 기준 변수(변수 1개 단위).</div>
  </div>
  <div class="input-row">
    <input bind:value={template} placeholder="폴더 이름 형식 (예: [value])" />
    <div class="muted">기본값은 [value] 입니다.</div>
  </div>
  <div class="toggle-row">
    <label>
      <input type="checkbox" bind:checked={dryRun} /> 드라이런
    </label>
    <label>
      <input type="checkbox" bind:checked={includeNegative} /> 네거티브 태그 포함
    </label>
  </div>
  <p class="muted">
    매칭 결과가 UNKNOWN/CONFLICT인 항목은 원래 폴더에 그대로 남습니다.
  </p>
  <ProgressBar
    label="폴더 분류 진행"
    status={displayStatus}
    detail={progressText}
    {processed}
    {total}
  />
</section>
