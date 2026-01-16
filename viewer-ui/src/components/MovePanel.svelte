<script lang="ts">
  import { onMount } from "svelte";
  import { template } from "../lib/stores";
  import { createJob, cancelJob, getThumbnailUrl, listTemplates, getTemplate, selectFolder } from "../lib/api";
  import { connectJob } from "../lib/ws";

  // 폴더 경로 (직접 입력)
  let sourceFolder = "";
  let targetFolder = "";
  let sameAsSource = false; // 원본=대상 옵션
  
  // 템플릿 선택
  let templateList: Array<{ id: number; name: string }> = [];
  let selectedTemplateName = "";
  
  // 변수 트리 (깊이별 변수 - 폴더 위계 구조)
  let varTree: string[] = [];
  let dragIdx: number | null = null;
  
  // 옵션
  let dryRun = true;
  let includeNegative = false;
  let resumeMode = false;
  let thumbs = true;
  
  // 필터
  let filters = { OK: true, PARTIAL: true, UNKNOWN: true, CONFLICT: true, ERROR: true, SKIP: true };
  
  // 상태
  let status = "대기";
  let processed = 0;
  let total = 0;
  let isRunning = false;
  let currentJobId: string | null = null;
  
  // 현재 보는 폴더 경로 (분류 결과 탐색용)
  let currentPath: string[] = [];
  
  // 결과
  interface ResultItem {
    status: "OK" | "PARTIAL" | "UNKNOWN" | "CONFLICT" | "ERROR" | "SKIP";
    source: string;
    target?: string;
    folder?: string; // 분류된 폴더 경로
    message?: string;
  }
  let results: ResultItem[] = [];
  let selectedResult: ResultItem | null = null;
  
  // 검색
  let searchQuery = "";
  let searchMode: "name" | "tag" = "name";
  let tagOperator: "AND" | "OR" = "AND";
  
  // 썸네일 로딩
  let thumbObserver: IntersectionObserver | null = null;
  const CHUNK_SIZE = 50;
  let loadedCount = 0;

  // 대상 폴더 자동 설정
  $: if (sameAsSource) {
    targetFolder = sourceFolder;
  }

  // 템플릿에서 사용 가능한 변수 목록 (트리에 없는 것만)
  $: availableVars = $template.variables.filter(v => !varTree.includes(v.name));
  
  // 폴더 구조 미리보기
  $: treePreview = varTree.length > 0 
    ? "대상폴더/" + varTree.map((v, i) => `${"  ".repeat(i)}[${v}값]/`).join("\n") 
    : "(변수를 추가하세요)";
  
  // 현재 경로에 맞는 결과 필터링
  $: pathFilteredResults = results.filter(r => {
    if (currentPath.length === 0) return true;
    const folderParts = (r.folder || "").split(/[/\\]/).filter(Boolean);
    return currentPath.every((p, i) => folderParts[i] === p);
  });
  
  // 정렬 함수
  function sortByName(arr: ResultItem[]): ResultItem[] {
    return [...arr].sort((a, b) => getFileName(a.source).localeCompare(getFileName(b.source), 'ko'));
  }
  
  // 검색 필터링
  $: searchFilteredResults = pathFilteredResults.filter(r => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    if (searchMode === "name") {
      return getFileName(r.source).toLowerCase().includes(query);
    } else {
      return getFileName(r.source).toLowerCase().includes(query);
    }
  });
  
  $: filteredResults = sortByName(searchFilteredResults.filter(r => filters[r.status]));
  
  // 현재 깊이에서 바로 보이는 아이템 (폴더 깊이가 정확히 일치하는 것들)
  $: currentLevelResults = filteredResults.filter(r => {
    const folderParts = (r.folder || "").split(/[/\\]/).filter(Boolean);
    return folderParts.length === currentPath.length;
  });
  
  $: displayResults = currentLevelResults.slice(0, loadedCount);
  $: resultStats = {
    ok: results.filter(r => r.status === "OK").length,
    partial: results.filter(r => r.status === "PARTIAL").length,
    unknown: results.filter(r => r.status === "UNKNOWN").length,
    conflict: results.filter(r => r.status === "CONFLICT").length,
    error: results.filter(r => r.status === "ERROR").length,
    skip: results.filter(r => r.status === "SKIP").length,
  };
  $: if (currentLevelResults) loadedCount = Math.min(CHUNK_SIZE, currentLevelResults.length);
  
  // 현재 깊이의 하위 폴더들과 각 폴더별 개수
  $: subFolderData = getSubFolderData(filteredResults, currentPath);

  interface FolderInfo {
    name: string;
    count: number;
    preview?: string; // 첫 번째 이미지 경로
  }

  function getSubFolderData(items: ResultItem[], path: string[]): FolderInfo[] {
    const folderMap = new Map<string, { count: number; preview?: string }>();
    items.forEach(r => {
      if (!r.folder) return;
      const parts = r.folder.split(/[/\\]/).filter(Boolean);
      if (path.every((p, i) => parts[i] === p) && parts.length > path.length) {
        const folderName = parts[path.length];
        const existing = folderMap.get(folderName);
        if (!existing) {
          folderMap.set(folderName, { count: 1, preview: r.source });
        } else {
          existing.count++;
        }
      }
    });
    return [...folderMap.entries()]
      .map(([name, data]) => ({ name, ...data }))
      .sort((a, b) => a.name.localeCompare(b.name, 'ko'));
  }
  
  // 하위 폴더 목록 (호환성)
  $: subFolders = subFolderData.map(f => f.name);

  onMount(async () => {
    setupObserver();
    await refreshTemplateList();
    return () => { if (thumbObserver) thumbObserver.disconnect(); };
  });
  
  async function refreshTemplateList() {
    try {
      templateList = await listTemplates();
    } catch (err) {
      console.error("템플릿 목록 로드 실패:", err);
    }
  }
  
  async function loadSelectedTemplate(name: string) {
    if (!name) return;
    try {
      const data = await getTemplate(name);
      console.log("Loaded template:", data);
      if (data && data.variables) {
        template.set({ name: data.name, variables: data.variables as any });
        selectedTemplateName = name;
        varTree = [];
        status = `"${name}" 템플릿 로드됨 (${data.variables.length}개 변수)`;
      } else {
        status = `템플릿에 변수가 없습니다`;
      }
    } catch (err) {
      status = `템플릿 로드 오류: ${err}`;
    }
  }

  function setupObserver() {
    if (thumbObserver) thumbObserver.disconnect();
    thumbObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target as HTMLImageElement;
          const src = img.dataset.src;
          if (src && img.src !== src) {
            img.src = src;
            img.onload = () => { img.style.opacity = "1"; };
            img.onerror = () => { img.style.display = "none"; };
          }
          thumbObserver?.unobserve(entry.target);
        }
      });
    }, { rootMargin: "200px" });
  }

  function observeThumb(node: HTMLImageElement) {
    if (thumbObserver) thumbObserver.observe(node);
    return { destroy() { if (thumbObserver) thumbObserver.unobserve(node); } };
  }

  function loadMore() {
    if (loadedCount < filteredResults.length) loadedCount = Math.min(loadedCount + CHUNK_SIZE, filteredResults.length);
  }

  function handleGridScroll(e: Event) {
    const el = e.target as HTMLElement;
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 300) loadMore();
  }

  async function openSourceDialog() {
    try {
      const path = await selectFolder();
      if (path) {
        sourceFolder = path;
        if (sameAsSource) targetFolder = path;
        status = `원본 폴더: ${path}`;
      }
    } catch (err) {
      status = `폴더 선택 오류: ${err}`;
    }
  }

  async function openTargetDialog() {
    try {
      const path = await selectFolder();
      if (path) {
        targetFolder = path;
        status = `대상 폴더: ${path}`;
      }
    } catch (err) {
      status = `폴더 선택 오류: ${err}`;
    }
  }
  
  // 변수 트리 관리
  function addVar(name: string) {
    if (!varTree.includes(name)) {
      varTree = [...varTree, name];
    }
  }
  
  function removeVar(idx: number) {
    varTree = varTree.filter((_, i) => i !== idx);
  }
  
  function handleDragStart(e: DragEvent, idx: number) {
    dragIdx = idx;
    if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
  }
  
  function handleDragOver(e: DragEvent, idx: number) {
    e.preventDefault();
    if (dragIdx !== null && dragIdx !== idx) {
      const newOrder = [...varTree];
      const [moved] = newOrder.splice(dragIdx, 1);
      newOrder.splice(idx, 0, moved);
      varTree = newOrder;
      dragIdx = idx;
    }
  }
  
  function handleDragEnd() { dragIdx = null; }
  
  // 폴더 탐색
  function navigateToFolder(folder: string) {
    currentPath = [...currentPath, folder];
    loadedCount = CHUNK_SIZE;
  }
  
  function navigateUp() {
    currentPath = currentPath.slice(0, -1);
    loadedCount = CHUNK_SIZE;
  }
  
  function navigateToRoot() {
    currentPath = [];
    loadedCount = CHUNK_SIZE;
  }

  async function runClassify() {
    if (!sourceFolder.trim()) { status = "원본 폴더를 선택하세요"; return; }
    if (!targetFolder.trim()) { status = "대상 폴더를 선택하세요"; return; }
    if (varTree.length === 0) { status = "분류 변수를 추가하세요"; return; }
    
    isRunning = true; status = "시작 중..."; processed = 0; total = 0; results = []; loadedCount = CHUNK_SIZE; currentPath = [];
    
    try {
      const response = await createJob("move", {
        folder: sourceFolder,  // source_folder -> folder
        target_root: targetFolder,  // target_folder -> target_root
        variable_tree: varTree,  // 계층별 분류: 변수 배열 전송
        include_negative: includeNegative, 
        dry_run: dryRun, 
        resume_mode: resumeMode, 
        thumbs, 
        variables: $template.variables
      });
      currentJobId = response.job_id;
      const conn = connectJob(response.job_id, (msg) => {
        if (msg.type === "progress") { processed = msg.processed || 0; total = msg.total || 0; status = `처리 중... ${processed}/${total}`; }
        else if (msg.type === "result") { results = [...results, { status: msg.status as ResultItem["status"], source: msg.source || "", target: msg.target, folder: msg.folder, message: msg.message }]; }
        else if (msg.type === "done") { status = `완료: ${processed}개 처리됨`; isRunning = false; currentJobId = null; conn.close(); }
        else if (msg.type === "error") { status = `오류: ${msg.message}`; isRunning = false; currentJobId = null; conn.close(); }
      });
    } catch (err) { status = `오류: ${err}`; isRunning = false; currentJobId = null; }
  }

  async function handleCancel() {
    if (currentJobId) {
      try { await cancelJob(currentJobId); status = "취소됨"; } catch (err) { status = `취소 실패: ${err}`; }
      isRunning = false; currentJobId = null;
    }
  }

  function getFileName(p: string): string { return p.split(/[/\\]/).pop() || p; }
  function selectItem(item: ResultItem) { selectedResult = item; }
  function toggleFilter(key: keyof typeof filters) { filters[key] = !filters[key]; filters = filters; }
</script>

<div class="panel">
  <header class="header">
    <!-- Row 1: 폴더 선택 -->
    <div class="row">
      <div class="field folder-field">
        <span class="lbl">원본 폴더</span>
        <div class="input-group">
          <input bind:value={sourceFolder} placeholder="폴더 경로" disabled={isRunning} />
          <button class="btn" on:click={openSourceDialog} disabled={isRunning}>폴더 선택</button>
        </div>
      </div>
      <div class="field same-check">
        <label>
          <input type="checkbox" bind:checked={sameAsSource} disabled={isRunning} />
          원본 폴더 내 분류
        </label>
      </div>
      <div class="field folder-field">
        <span class="lbl">대상 폴더</span>
        <div class="input-group">
          <input bind:value={targetFolder} placeholder="결과 저장 폴더" disabled={sameAsSource || isRunning} />
          <button class="btn" on:click={openTargetDialog} disabled={isRunning || sameAsSource}>폴더 선택</button>
        </div>
      </div>
    </div>
    
    <!-- Row 2: 템플릿 + 변수 트리 -->
    <div class="row">
      <div class="field template-field">
        <span class="lbl">템플릿</span>
        <select on:change={e => loadSelectedTemplate(e.currentTarget.value)} disabled={isRunning}>
          <option value="">템플릿 선택...</option>
          {#each templateList as t}<option value={t.name}>{t.name}</option>{/each}
        </select>
      </div>
      <div class="field tree-field">
        <span class="lbl">폴더 위계 (깊이별 변수, 드래그로 순서 변경)</span>
        <div class="tree-container">
          <div class="tree-chips">
            {#each varTree as name, idx}
              <div class="tree-chip" draggable="true" class:dragging={dragIdx === idx}
                on:dragstart={e => handleDragStart(e, idx)}
                on:dragover={e => handleDragOver(e, idx)}
                on:dragend={handleDragEnd}>
                <span class="depth">L{idx + 1}</span>
                <span class="name">{name}</span>
                <button class="del" on:click={() => removeVar(idx)}>×</button>
              </div>
            {:else}
              <span class="placeholder">변수를 추가하세요 →</span>
            {/each}
          </div>
          <div class="add-vars">
            {#each availableVars as v}
              <button class="add-chip" on:click={() => addVar(v.name)} disabled={isRunning}>+ {v.name}</button>
            {:else}
              {#if $template.variables.length === 0}
                <span class="hint">템플릿을 먼저 선택</span>
              {:else}
                <span class="hint">모든 변수 추가됨</span>
              {/if}
            {/each}
          </div>
        </div>
      </div>
      <div class="field preview-field">
        <span class="lbl">구조 미리보기</span>
        <pre class="tree-preview">{treePreview}</pre>
      </div>
    </div>
    
    <!-- Row 3: 옵션 + 필터 + 실행 -->
    <div class="row">
      <div class="opts">
        <label><input type="checkbox" bind:checked={dryRun} disabled={isRunning}/> 드라이런</label>
        <label><input type="checkbox" bind:checked={includeNegative} disabled={isRunning}/> 네거티브</label>
        <label><input type="checkbox" bind:checked={resumeMode} disabled={isRunning}/> 재개</label>
        <label><input type="checkbox" bind:checked={thumbs} disabled={isRunning}/> 썸네일</label>
      </div>
      <div class="filter-btns">
        <button class="fbtn" class:on={filters.OK} on:click={() => toggleFilter("OK")}>OK <b>{resultStats.ok}</b></button>
        <button class="fbtn part" class:on={filters.PARTIAL} on:click={() => toggleFilter("PARTIAL")}>PAR <b>{resultStats.partial}</b></button>
        <button class="fbtn" class:on={filters.UNKNOWN} on:click={() => toggleFilter("UNKNOWN")}>UNK <b>{resultStats.unknown}</b></button>
        <button class="fbtn warn" class:on={filters.CONFLICT} on:click={() => toggleFilter("CONFLICT")}>CON <b>{resultStats.conflict}</b></button>
        <button class="fbtn err" class:on={filters.ERROR} on:click={() => toggleFilter("ERROR")}>ERR <b>{resultStats.error}</b></button>
      </div>
      <div class="acts">
        {#if total > 0 || isRunning}
          <div class="prog">
            <div class="bar"><div class="fill" style="width:{total?processed/total*100:0}%"></div></div>
            <span>{processed}/{total}</span>
          </div>
        {/if}
        {#if isRunning}
          <button class="btn danger" on:click={handleCancel}>취소</button>
        {:else}
          <button class="btn primary" on:click={runClassify}>실행</button>
        {/if}
        <span class="status">{status}</span>
      </div>
    </div>
  </header>

  <div class="body">
    <main class="thumbs" on:scroll={handleGridScroll}>
      <!-- 경로 탐색 바 -->
      <div class="path-bar">
        <div class="breadcrumb">
          <button class="crumb root" on:click={navigateToRoot}>📁 루트</button>
          {#each currentPath as folder, i}
            <span class="sep">/</span>
            <button class="crumb" on:click={() => currentPath = currentPath.slice(0, i + 1)}>{folder}</button>
          {/each}
        </div>
        {#if currentPath.length > 0}
          <button class="btn-up" on:click={navigateUp}>⬆ 상위 폴더</button>
        {/if}
        <!-- 검색 -->
        <div class="search-inline">
          <input bind:value={searchQuery} placeholder="검색..." />
        </div>
      </div>
      
      {#if subFolderData.length > 0 || displayResults.length > 0}
        <div class="grid">
          <!-- 폴더들 먼저 표시 -->
          {#each subFolderData as folder}
            <div class="card folder-card" on:click={() => navigateToFolder(folder.name)}>
              <div class="img folder-img">
                {#if folder.preview}
                  <img src={getThumbnailUrl(folder.preview)} alt={folder.name} />
                {/if}
                <div class="folder-overlay">
                  <span class="folder-icon">📁</span>
                </div>
              </div>
              <div class="cap">
                <span class="fn folder-name">{folder.name}</span>
                <span class="ftag">{folder.count}개 이미지</span>
              </div>
            </div>
          {/each}
          
          <!-- 현재 깊이의 이미지들 -->
          {#each displayResults as item}
            <div class="card {item.status.toLowerCase()}" class:sel={selectedResult === item} on:click={() => selectItem(item)}>
              <div class="img">
                <div class="ph">▦</div>
                <img data-src={getThumbnailUrl(item.source)} alt={getFileName(item.source)} use:observeThumb />
              </div>
              <div class="cap">
                <span class="badge {item.status.toLowerCase()}">{item.status}</span>
                <span class="fn">{getFileName(item.source)}</span>
              </div>
            </div>
          {/each}
        </div>
        {#if loadedCount < currentLevelResults.length}
          <div class="more"><button class="btn ghost" on:click={loadMore}>더 보기 ({currentLevelResults.length - loadedCount})</button></div>
        {/if}
      {:else}
        <div class="empty-state">
          <div class="icon">📁</div>
          <div>결과가 없습니다</div>
          <div class="hint">폴더를 선택하고 실행하세요</div>
        </div>
      {/if}
    </main>
  </div>

  {#if selectedResult}
    <div class="detail">
      <div class="dhead"><span>상세</span><button on:click={() => selectedResult = null}>×</button></div>
      <img src={getThumbnailUrl(selectedResult.source)} alt="preview" on:error={(e) => { e.currentTarget.style.display='none'; }}/>
      <div class="dinfo">
        <div><b>상태:</b><span class="badge {selectedResult.status.toLowerCase()}">{selectedResult.status}</span></div>
        <div><b>파일:</b>{getFileName(selectedResult.source)}</div>
        {#if selectedResult.folder}<div><b>분류:</b><span class="ftag">{selectedResult.folder}</span></div>{/if}
        {#if selectedResult.target}<div><b>경로:</b>{selectedResult.target}</div>{/if}
        {#if selectedResult.message}<div><b>메시지:</b>{selectedResult.message}</div>{/if}
      </div>
    </div>
  {/if}
</div>

<style>
.panel{display:flex;flex-direction:column;height:100%;gap:12px;overflow:hidden}
.header{background:var(--panel);border-radius:var(--radius);padding:14px 16px;flex-shrink:0}
.row{display:flex;gap:16px;align-items:flex-end;flex-wrap:wrap}
.row+.row{margin-top:12px}
.field{display:flex;flex-direction:column;gap:4px}
.field .lbl{font-size:11px;color:var(--text-muted)}
.folder-field{flex:1;min-width:200px}
.same-check{justify-content:flex-end}
.same-check label{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--text-muted);cursor:pointer;padding:6px 0}
.template-field{width:160px}
.template-field select{padding:6px 10px;background:var(--bg);border:1px solid rgba(255,255,255,0.08);border-radius:6px;color:var(--text);font-size:11px}
.tree-field{flex:2;min-width:300px}
.preview-field{min-width:180px}
.tree-preview{display:block;padding:6px 10px;background:var(--bg);border-radius:6px;font-size:10px;color:var(--accent);font-family:monospace;margin:0;white-space:pre;line-height:1.4}
.input-group{display:flex;gap:6px}
.input-group input{flex:1;padding:6px 10px;background:var(--bg);border:1px solid rgba(255,255,255,0.08);border-radius:6px;color:var(--text);font-size:12px}
.tree-container{display:flex;flex-direction:column;gap:6px;padding:8px;background:var(--bg);border-radius:6px}
.tree-chips{display:flex;gap:6px;flex-wrap:wrap;min-height:28px}
.tree-chip{display:flex;align-items:center;gap:4px;padding:4px 8px;background:var(--accent);color:var(--bg);border-radius:14px;cursor:grab;user-select:none;font-size:11px}
.tree-chip.dragging{opacity:0.5;transform:scale(0.95)}
.tree-chip .depth{font-size:9px;font-weight:700;background:rgba(0,0,0,0.2);padding:1px 4px;border-radius:8px}
.tree-chip .del{background:none;border:none;color:inherit;cursor:pointer;opacity:0.6;font-size:12px;padding:0 2px}
.tree-chip .del:hover{opacity:1}
.tree-chips .placeholder{font-size:11px;color:var(--text-muted)}
.add-vars{display:flex;gap:4px;flex-wrap:wrap}
.add-chip{padding:3px 8px;background:var(--panel-2);border:1px dashed rgba(255,255,255,0.15);border-radius:12px;color:var(--text-muted);font-size:10px;cursor:pointer}
.add-chip:hover{border-color:var(--accent);color:var(--accent)}
.add-chip:disabled{opacity:0.4;cursor:not-allowed}
.add-vars .hint{font-size:10px;color:var(--text-muted);padding:4px}
.opts{display:flex;gap:12px;align-items:center}
.opts label{display:flex;align-items:center;gap:4px;font-size:11px;color:var(--text-muted);cursor:pointer}
.filter-btns{display:flex;gap:4px}
.fbtn{padding:4px 8px;background:var(--bg);border:1px solid rgba(255,255,255,0.08);border-radius:6px;font-size:10px;color:var(--text-muted);cursor:pointer;transition:all 0.15s}
.fbtn:hover{border-color:rgba(255,255,255,0.2)}
.fbtn.on{background:var(--accent);color:var(--bg);border-color:var(--accent)}
.fbtn.part.on{background:#06b6d4;border-color:#06b6d4}
.fbtn.warn.on{background:#f59e0b;border-color:#f59e0b}
.fbtn.err.on{background:var(--danger);border-color:var(--danger)}
.fbtn b{font-weight:500;margin-left:3px}
.acts{display:flex;gap:8px;align-items:center;margin-left:auto}
.prog{display:flex;align-items:center;gap:6px}
.prog .bar{width:80px;height:6px;background:var(--bg);border-radius:3px;overflow:hidden}
.prog .fill{height:100%;background:var(--accent);transition:width 0.2s}
.prog span{font-size:10px;color:var(--text-muted)}
.status{font-size:11px;color:var(--accent)}
.btn{padding:6px 12px;background:var(--panel-2);border:none;border-radius:6px;color:var(--text);font-size:12px;font-weight:600;cursor:pointer;white-space:nowrap}
.btn:hover{background:var(--bg)}
.btn:disabled{opacity:0.5;cursor:not-allowed}
.btn.primary{background:var(--accent);color:var(--bg)}
.btn.primary:hover{background:var(--accent-2)}
.btn.danger{background:var(--danger);color:#fff}
.btn.ghost{background:transparent}
.body{display:flex;flex:1;gap:12px;overflow:hidden}
.thumbs{flex:1;background:var(--panel);border-radius:var(--radius);overflow-y:auto;display:flex;flex-direction:column;min-width:0}
.path-bar{display:flex;align-items:center;gap:12px;padding:10px 14px;border-bottom:1px solid rgba(255,255,255,0.06);flex-shrink:0;flex-wrap:wrap}
.breadcrumb{display:flex;align-items:center;gap:4px;flex:1;overflow:hidden}
.crumb{background:var(--bg);border:none;color:var(--text);font-size:11px;cursor:pointer;padding:4px 8px;border-radius:6px;white-space:nowrap}
.crumb:hover{background:var(--panel-2)}
.crumb.root{font-weight:600}
.sep{color:var(--text-muted);font-size:12px}
.btn-up{padding:4px 10px;background:var(--bg);border:none;border-radius:6px;color:var(--text-muted);font-size:11px;cursor:pointer}
.btn-up:hover{color:var(--text);background:var(--panel-2)}
.search-inline{width:180px}
.search-inline input{width:100%;padding:5px 10px;background:var(--bg);border:1px solid rgba(255,255,255,0.08);border-radius:6px;color:var(--text);font-size:11px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px;padding:12px}
.card{background:var(--bg);border-radius:8px;overflow:hidden;cursor:pointer;transition:transform 0.15s,box-shadow 0.15s;border:2px solid transparent}
.card:hover{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,0.3)}
.card.sel{border-color:var(--accent)}
.card.ok{border-color:rgba(34,197,94,0.4)}
.card.partial{border-color:rgba(6,182,212,0.4)}
.card.conflict{border-color:rgba(245,158,11,0.4)}
.card.error{border-color:rgba(239,68,68,0.4)}
.card.unknown{border-color:rgba(99,102,241,0.4)}
.folder-card{border-color:rgba(255,255,255,0.1)}
.folder-card:hover{border-color:var(--accent);transform:translateY(-3px)}
.img{aspect-ratio:1;position:relative;background:var(--panel)}
.img .ph{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:28px;color:var(--text-muted);opacity:0.3}
.img img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0;transition:opacity 0.3s}
.img img.loaded{opacity:1}
.folder-img{background:linear-gradient(135deg,var(--panel) 0%,var(--bg) 100%)}
.folder-img img{opacity:0.4;filter:blur(2px)}
.folder-overlay{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.3)}
.folder-icon{font-size:40px;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.3))}
.cap{padding:8px;display:flex;flex-direction:column;gap:4px}
.cap .fn{font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cap .folder-name{font-weight:600;font-size:11px}
.cap .ftag{font-size:9px;color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.badge{padding:2px 6px;border-radius:4px;font-size:9px;font-weight:600;text-transform:uppercase;width:fit-content}
.badge.ok{background:#22c55e;color:#fff}
.badge.partial{background:#06b6d4;color:#fff}
.badge.unknown{background:#6366f1;color:#fff}
.badge.conflict{background:#f59e0b;color:#fff}
.badge.error{background:var(--danger);color:#fff}
.badge.skip{background:#64748b;color:#fff}
.more{padding:16px;text-align:center}
.empty-state{display:flex;flex-direction:column;align-items:center;justify-content:center;flex:1;gap:8px;color:var(--text-muted)}
.empty-state .icon{font-size:48px;opacity:0.3}
.empty-state .hint{font-size:12px;opacity:0.6}
.detail{position:fixed;right:16px;bottom:16px;width:260px;background:var(--panel);border-radius:var(--radius);box-shadow:0 8px 32px rgba(0,0,0,0.4);overflow:hidden;z-index:100}
.dhead{display:flex;justify-content:space-between;align-items:center;padding:10px 12px;font-weight:600;font-size:12px;border-bottom:1px solid rgba(255,255,255,0.06)}
.dhead button{background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:14px}
.detail>img{width:100%;aspect-ratio:1;object-fit:contain;background:var(--bg)}
.dinfo{padding:10px 12px;font-size:11px;display:flex;flex-direction:column;gap:6px}
.dinfo div{display:flex;gap:6px;align-items:flex-start;flex-wrap:wrap}
.dinfo b{color:var(--text-muted);min-width:45px}
</style>
