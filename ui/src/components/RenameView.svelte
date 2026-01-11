<script lang="ts">
  import { pickFolder } from "../lib/dialog";
  import type { PresetVariable } from "../lib/preset";

  export let variables: PresetVariable[] = [];
  export let status = "대기";
  export let progressText = "";
  export let onRun: (payload: {
    folder: string;
    order: string[];
    template: string;
    prefixMode: boolean;
    dryRun: boolean;
    includeNegative: boolean;
  }) => void;
  export let disabled = false;

  let folder = "";
  let template = "";
  let prefixMode = false;
  let dryRun = true;
  let includeNegative = false;
  let localStatus = "";
  let order: string[] = [];
  let selectedVar = "";

  $: displayStatus = localStatus || status;
  $: availableNames = variables.map((variable) => variable.name);
  $: if (!selectedVar && availableNames.length > 0) {
    selectedVar = availableNames[0];
  }

  async function selectFolder() {
    const selected = await pickFolder();
    if (selected) {
      folder = selected;
      localStatus = "";
    }
  }

  function addOrder() {
    if (!selectedVar) {
      return;
    }
    if (order.includes(selectedVar)) {
      localStatus = "이미 추가된 변수입니다.";
      return;
    }
    order = [...order, selectedVar];
    localStatus = "";
  }

  function setAutoOrder() {
    if (availableNames.length === 0) {
      localStatus = "변수가 없습니다.";
      return;
    }
    order = [...availableNames];
    localStatus = "";
  }

  function clearOrder() {
    order = [];
  }

  function moveOrder(index: number, direction: number) {
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= order.length) {
      return;
    }
    const next = [...order];
    [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
    order = next;
  }

  function removeOrder(index: number) {
    const next = [...order];
    next.splice(index, 1);
    order = next;
  }

  function runRename() {
    if (!folder.trim()) {
      localStatus = "폴더를 입력하세요.";
      return;
    }
    if (order.length === 0) {
      localStatus = "변수 순서를 추가하세요.";
      return;
    }
    localStatus = "";
    onRun({
      folder,
      order,
      template: template.trim(),
      prefixMode,
      dryRun,
      includeNegative,
    });
  }
</script>

<section class="panel">
  <div class="section-title">
    <h2>파일명 변경</h2>
    <span class="badge">IPC 준비</span>
  </div>
  <div class="input-row">
    <input bind:value={folder} placeholder="작업 폴더 경로" />
    <div class="button-row">
      <button class="ghost" on:click={selectFolder} disabled={disabled}>찾기</button>
      <button class="primary" on:click={runRename} disabled={disabled}>실행</button>
    </div>
  </div>
  <div class="input-row">
    <input
      bind:value={template}
      placeholder="파일명 형식 (예: [character]_[emotion])"
    />
    <div class="muted">비워두면 변수 순서대로 자동 생성됩니다.</div>
  </div>
  <div class="panel inner">
    <div class="section-title small">
      <h3>변수 순서</h3>
    </div>
    <div class="input-row">
      <select bind:value={selectedVar} disabled={availableNames.length === 0}>
        {#each availableNames as name}
          <option value={name}>{name}</option>
        {/each}
      </select>
      <div class="button-row">
        <button class="ghost" on:click={addOrder} disabled={availableNames.length === 0}>
          추가
        </button>
        <button class="ghost" on:click={setAutoOrder} disabled={availableNames.length === 0}>
          자동 채우기
        </button>
        <button class="ghost" on:click={clearOrder} disabled={order.length === 0}>
          비우기
        </button>
      </div>
    </div>
    <div class="list">
      {#if order.length === 0}
        <div class="muted">순서를 추가하면 여기 표시됩니다.</div>
      {:else}
        {#each order as name, index}
          <div class="list-row">
            <span>{index + 1}. {name}</span>
            <span class="spacer"></span>
            <div class="button-row">
              <button class="ghost small" on:click={() => moveOrder(index, -1)}>▲</button>
              <button class="ghost small" on:click={() => moveOrder(index, 1)}>▼</button>
              <button class="ghost small" on:click={() => removeOrder(index)}>삭제</button>
            </div>
          </div>
        {/each}
      {/if}
    </div>
  </div>
  <div class="toggle-row">
    <label>
      <input type="checkbox" bind:checked={prefixMode} /> 접두사 모드
    </label>
    <label>
      <input type="checkbox" bind:checked={dryRun} /> 드라이런
    </label>
    <label>
      <input type="checkbox" bind:checked={includeNegative} /> 네거티브 태그 포함
    </label>
  </div>
  <p class="muted">
    접두사 모드는 기존 파일명 앞에 형식을 붙이고, 드라이런은 실제 변경 없이 결과만
    확인합니다. 충돌 시 @@@숫자가 자동 부여됩니다.
  </p>
  <p>상태: {displayStatus}</p>
  {#if progressText}
    <p>{progressText}</p>
  {/if}
</section>
