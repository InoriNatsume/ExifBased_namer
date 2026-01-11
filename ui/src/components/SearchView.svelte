<script lang="ts">
  import { pickFolder } from "../lib/dialog";

  export let status = "대기";
  export let progressText = "";
  export let onSearch: (payload: {
    folder: string;
    tags: string;
    includeNegative: boolean;
  }) => void;
  export let onScan: (payload: {
    folder: string;
    includeNegative: boolean;
    incremental: boolean;
  }) => void;
  export let disabled = false;

  let folder = "";
  let tags = "";
  let includeNegative = false;
  let incremental = true;
  let localStatus = "";
  $: displayStatus = localStatus || status;

  async function selectFolder() {
    const selected = await pickFolder();
    if (selected) {
      folder = selected;
      localStatus = "";
    }
  }

  function runSearch() {
    if (!folder.trim()) {
      localStatus = "폴더를 입력하세요.";
      return;
    }
    if (!tags.trim()) {
      localStatus = "필수 태그를 입력하세요.";
      return;
    }
    localStatus = "";
    onSearch({ folder, tags, includeNegative });
  }

  function runScan() {
    if (!folder.trim()) {
      localStatus = "폴더를 입력하세요.";
      return;
    }
    localStatus = "";
    onScan({ folder, includeNegative, incremental });
  }
</script>

<section class="panel">
  <div class="section-title">
    <h2>검색</h2>
    <span class="badge">IPC 준비</span>
  </div>
  <div class="input-row">
    <input bind:value={folder} placeholder="작업 폴더 경로" />
    <div class="button-row">
      <button class="ghost" on:click={selectFolder} disabled={disabled}>찾기</button>
      <button class="primary" on:click={runSearch} disabled={disabled}>검색 테스트</button>
    </div>
  </div>
  <div class="input-row">
    <input bind:value={tags} placeholder="필수 태그 (쉼표 구분)" />
    <button class="primary" on:click={runScan} disabled={disabled}>DB 스캔</button>
  </div>
  <div class="toggle-row">
    <label>
      <input type="checkbox" bind:checked={includeNegative} /> 네거티브 태그 포함
    </label>
    <label>
      <input type="checkbox" bind:checked={incremental} /> 증분 스캔
    </label>
  </div>
  <p class="muted">
    DB 스캔은 폴더 전체의 태그를 DB에 저장해 검색과 분류 속도를 높입니다. 증분
    스캔은 이미 처리한 파일을 건너뜁니다.
  </p>
  <p>상태: {displayStatus}</p>
  {#if progressText}
    <p>{progressText}</p>
  {/if}
</section>
