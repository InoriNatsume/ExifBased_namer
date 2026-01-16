<script lang="ts">
  import { template } from "../lib/stores";
  import { 
    listTemplates, getTemplate, saveTemplate, deleteTemplate,
    buildPresetFromFolder,
    type PresetValue
  } from "../lib/api";
  
  // File input refs
  let fileInput: HTMLInputElement;
  let presetFileInput: HTMLInputElement;

  // State
  let templateList: Array<{ id: number; name: string }> = [];
  let selectedTemplateName: string | null = null;
  let status = "";
  
  // Variable/Value selection
  let selectedVarIndex: number | null = null;
  let selectedValIndex: number | null = null;
  
  // Add new
  let newVariableName = "";
  let newValueName = "";
  let newValueTags = "";
  
  // Import modal tabs
  let importTab: "file" | "folder" = "file";
  
  // Tag editing (하단 패널)
  $: editingValue = (selectedVarIndex !== null && selectedValIndex !== null) 
    ? $template.variables[selectedVarIndex]?.values[selectedValIndex] 
    : null;
  let editName = "";
  let editTags = "";
  let lastEditKey = "";
  
  $: {
    const key = `${selectedVarIndex}-${selectedValIndex}`;
    if (editingValue && key !== lastEditKey) {
      lastEditKey = key;
      editName = editingValue.name;
      editTags = editingValue.tags.join(", ");
    }
  }
  
  // Bulk operations
  let bulkPrefix = "";
  let bulkSuffix = "";
  let bulkFind = "";
  let bulkReplace = "";
  let bulkRemove = "";
  let bulkTagRemove = "";
  
  // Build from folder
  let buildFolder = "";
  let buildIncludeNegative = false;
  let buildTargetVar = "__new__";
  let buildNewVarName = "";
  let buildMode: "replace" | "append" = "replace";
  let buildStatus = "";
  let buildCommonTags: string[] = [];
  
  // Preset import
  let showImportModal = false;
  let importTargetVar = "";
  let importStatus = "";

  // Computed
  $: selectedVar = selectedVarIndex !== null ? $template.variables[selectedVarIndex] : null;
  $: selectedValue = selectedVar && selectedValIndex !== null ? selectedVar.values[selectedValIndex] : null;

  // Load templates on mount
  refreshList();

  async function refreshList() {
    try {
      templateList = await listTemplates();
      status = `${templateList.length}개 템플릿`;
    } catch (err) {
      status = `오류: ${err}`;
    }
  }

  async function loadTemplate(name: string) {
    try {
      const data = await getTemplate(name);
      if (data) {
        template.set(data as any);
        selectedTemplateName = name;
        selectedVarIndex = null;
        selectedValIndex = null;
        status = `"${name}" 불러옴`;
      }
    } catch (err) {
      status = `오류: ${err}`;
    }
  }

  async function handleSave() {
    const name = $template.name?.trim();
    if (!name) { status = "템플릿 이름을 입력하세요"; return; }
    try {
      await saveTemplate(name, $template);
      await refreshList();
      status = `"${name}" 저장됨`;
    } catch (err) {
      status = `오류: ${err}`;
    }
  }

  async function handleDelete(name: string) {
    if (!confirm(`"${name}" 템플릿을 삭제하시겠습니까?`)) return;
    try {
      await deleteTemplate(name);
      await refreshList();
      if (selectedTemplateName === name) {
        selectedTemplateName = null;
        template.set({ name: null, variables: [] });
      }
      status = `"${name}" 삭제됨`;
    } catch (err) {
      status = `오류: ${err}`;
    }
  }

  function clearTemplate() {
    template.set({ name: null, variables: [] });
    selectedTemplateName = null;
    selectedVarIndex = null;
    selectedValIndex = null;
    status = "새 템플릿";
  }

  function addVariable() {
    const name = newVariableName.trim() || `변수 ${$template.variables.length + 1}`;
    if ($template.variables.some(v => v.name === name)) { status = "이미 존재하는 변수명"; return; }
    template.update(t => ({ ...t, variables: [...t.variables, { name, values: [] }] }));
    selectedVarIndex = $template.variables.length - 1;
    newVariableName = "";
    status = `변수 "${name}" 추가됨`;
  }

  function deleteVariable(idx: number) {
    template.update(t => ({ ...t, variables: t.variables.filter((_, i) => i !== idx) }));
    if (selectedVarIndex === idx) { selectedVarIndex = null; selectedValIndex = null; }
    status = "변수 삭제됨";
  }

  function addValue() {
    if (selectedVarIndex === null) { status = "변수를 먼저 선택하세요"; return; }
    const name = newValueName.trim() || `값 ${$template.variables[selectedVarIndex].values.length + 1}`;
    const tags = newValueTags.split(",").map(t => t.trim()).filter(Boolean);
    template.update(t => {
      const vars = [...t.variables];
      vars[selectedVarIndex!] = { ...vars[selectedVarIndex!], values: [...vars[selectedVarIndex!].values, { name, tags }] };
      return { ...t, variables: vars };
    });
    newValueName = "";
    newValueTags = "";
    status = `값 "${name}" 추가됨`;
  }

  function deleteValue(varIdx: number, valIdx: number) {
    template.update(t => {
      const vars = [...t.variables];
      vars[varIdx] = { ...vars[varIdx], values: vars[varIdx].values.filter((_, i) => i !== valIdx) };
      return { ...t, variables: vars };
    });
    if (selectedValIndex === valIdx) selectedValIndex = null;
    status = "값 삭제됨";
  }

  function selectValue(varIdx: number, valIdx: number) {
    selectedVarIndex = varIdx;
    selectedValIndex = valIdx;
  }

  // === Tag editing ===
  function saveEditValue() {
    if (selectedVarIndex === null || selectedValIndex === null) return;
    const tagList = editTags.split(",").map(t => t.trim()).filter(Boolean);
    template.update(t => {
      const vars = [...t.variables];
      const values = [...vars[selectedVarIndex!].values];
      values[selectedValIndex!] = { name: editName.trim() || values[selectedValIndex!].name, tags: tagList };
      vars[selectedVarIndex!] = { ...vars[selectedVarIndex!], values };
      return { ...t, variables: vars };
    });
    status = "값 저장됨";
  }

  // === Bulk name operations ===
  function applyBulkPrefix() {
    if (!bulkPrefix.trim() || selectedVarIndex === null) return;
    template.update(t => {
      const vars = [...t.variables];
      vars[selectedVarIndex!] = { 
        ...vars[selectedVarIndex!], 
        values: vars[selectedVarIndex!].values.map(v => ({ ...v, name: bulkPrefix + v.name }))
      };
      return { ...t, variables: vars };
    });
    status = "앞에 추가 적용됨";
  }

  function applyBulkSuffix() {
    if (!bulkSuffix.trim() || selectedVarIndex === null) return;
    template.update(t => {
      const vars = [...t.variables];
      vars[selectedVarIndex!] = { 
        ...vars[selectedVarIndex!], 
        values: vars[selectedVarIndex!].values.map(v => ({ ...v, name: v.name + bulkSuffix }))
      };
      return { ...t, variables: vars };
    });
    status = "뒤에 추가 적용됨";
  }

  function applyBulkReplace() {
    if (!bulkFind.trim() || selectedVarIndex === null) return;
    template.update(t => {
      const vars = [...t.variables];
      vars[selectedVarIndex!] = { 
        ...vars[selectedVarIndex!], 
        values: vars[selectedVarIndex!].values.map(v => ({ ...v, name: v.name.replaceAll(bulkFind, bulkReplace) }))
      };
      return { ...t, variables: vars };
    });
    status = "찾기/바꾸기 적용됨";
  }

  function applyBulkRemove() {
    if (!bulkRemove.trim() || selectedVarIndex === null) return;
    template.update(t => {
      const vars = [...t.variables];
      vars[selectedVarIndex!] = { 
        ...vars[selectedVarIndex!], 
        values: vars[selectedVarIndex!].values.map(v => ({ ...v, name: v.name.replaceAll(bulkRemove, "") }))
      };
      return { ...t, variables: vars };
    });
    status = "삭제 적용됨";
  }

  // === Bulk tag operations ===
  function removeCommonTags() {
    if (selectedVarIndex === null) return;
    const values = $template.variables[selectedVarIndex].values;
    if (values.length < 2) { status = "값이 2개 이상이어야 합니다"; return; }
    
    // Find common tags
    const tagSets = values.map(v => new Set(v.tags));
    const common = [...tagSets[0]].filter(tag => tagSets.every(s => s.has(tag)));
    if (common.length === 0) { status = "공통 태그 없음"; return; }
    
    template.update(t => {
      const vars = [...t.variables];
      vars[selectedVarIndex!] = { 
        ...vars[selectedVarIndex!], 
        values: vars[selectedVarIndex!].values.map(v => ({ 
          ...v, 
          tags: v.tags.filter(tag => !common.includes(tag))
        }))
      };
      return { ...t, variables: vars };
    });
    status = `공통 태그 ${common.length}개 제거됨: ${common.slice(0,5).join(", ")}${common.length > 5 ? "..." : ""}`;
  }

  function removeTagsFromAll() {
    if (!bulkTagRemove.trim() || selectedVarIndex === null) return;
    const tagsToRemove = bulkTagRemove.split(",").map(t => t.trim()).filter(Boolean);
    template.update(t => {
      const vars = [...t.variables];
      vars[selectedVarIndex!] = { 
        ...vars[selectedVarIndex!], 
        values: vars[selectedVarIndex!].values.map(v => ({ 
          ...v, 
          tags: v.tags.filter(tag => !tagsToRemove.includes(tag))
        }))
      };
      return { ...t, variables: vars };
    });
    status = `태그 ${tagsToRemove.length}개 삭제됨`;
    bulkTagRemove = "";
  }

  // === Build from folder ===
  function triggerBuildFolderSelect() {
    const path = prompt("이미지가 있는 폴더 경로를 입력하세요:");
    if (path) buildFolder = path;
  }

  async function handleBuild() {
    if (!buildFolder.trim()) { buildStatus = "폴더 경로를 입력하세요"; return; }
    const targetName = buildTargetVar === "__new__" ? buildNewVarName.trim() : buildTargetVar;
    if (!targetName) { buildStatus = "변수 이름을 입력하세요"; return; }
    
    try {
      buildStatus = "분석 중...";
      const result = await buildPresetFromFolder(buildFolder, buildIncludeNegative);
      if (!result?.values?.length) { buildStatus = "값을 찾을 수 없습니다"; return; }
      
      buildCommonTags = result.common_tags || [];
      
      template.update(t => {
        const vars = [...t.variables];
        const idx = vars.findIndex(v => v.name === targetName);
        if (idx >= 0) {
          if (buildMode === "append") {
            vars[idx] = { ...vars[idx], values: [...vars[idx].values, ...result.values] };
          } else {
            vars[idx] = { ...vars[idx], values: result.values };
          }
        } else {
          vars.push({ name: targetName, values: result.values });
        }
        return { ...t, variables: vars };
      });
      buildStatus = `${result.values.length}개 값 생성됨`;
    } catch (err) {
      buildStatus = `오류: ${err}`;
    }
  }

  async function handleBuildAndClose() {
    await handleBuild();
    if (buildStatus.includes("개 값 생성")) {
      showImportModal = false;
    }
  }

  // === File operations ===
  function triggerFileInput() { fileInput?.click(); }
  
  function handleFileInputChange(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result as string);
        template.set(data);
        status = `"${file.name}"에서 불러옴`;
      } catch (err) {
        status = `JSON 파싱 오류: ${err}`;
      }
    };
    reader.onerror = () => { status = `파일 읽기 오류`; };
    reader.readAsText(file);
    input.value = "";
  }
  
  function downloadTemplate() {
    const name = $template.name?.trim() || "template";
    const json = JSON.stringify($template, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${name}.json`;
    a.click();
    URL.revokeObjectURL(url);
    status = `"${name}.json" 다운로드됨`;
  }

  // === Preset import (nais/sdstudio) ===
  function triggerPresetFileInput() { presetFileInput?.click(); }
  
  async function handlePresetFileInputChange(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    
    try {
      importStatus = "가져오는 중...";
      
      const formData = new FormData();
      formData.append("file", file);
      
      const API_BASE = import.meta.env.DEV ? "http://localhost:8000" : "";
      const res = await fetch(`${API_BASE}/api/preset/parse-file`, {
        method: "POST",
        body: formData
      });
      
      if (!res.ok) throw new Error(await res.text());
      const result = await res.json();
      
      if (!result?.values?.length) { 
        importStatus = "가져올 값이 없습니다"; 
        input.value = "";
        return; 
      }
      
      const targetVarName = importTargetVar.trim() || result.variable_name || file.name.replace(/\.[^/.]+$/, "");
      template.update(t => {
        const vars = [...t.variables];
        const idx = vars.findIndex(v => v.name === targetVarName);
        if (idx >= 0) vars[idx] = { ...vars[idx], values: result.values };
        else vars.push({ name: targetVarName, values: result.values });
        return { ...t, variables: vars };
      });
      importStatus = `${result.values.length}개 값 가져옴`;
      showImportModal = false;
    } catch (err) {
      importStatus = `오류: ${err}`;
    }
    input.value = "";
  }
</script>

<!-- Hidden file inputs -->
<input type="file" accept=".json" bind:this={fileInput} on:change={handleFileInputChange} style="display:none" />
<input type="file" accept=".nai,.txt,.json" bind:this={presetFileInput} on:change={handlePresetFileInputChange} style="display:none" />

<div class="editor">
  <!-- Header -->
  <header class="header">
    <div class="name-area">
      <input bind:value={$template.name} placeholder="템플릿 이름" class="template-name" />
      <span class="count">{$template.variables.length}개 변수</span>
    </div>
    <div class="actions">
      <select on:change={(e) => e.currentTarget.value && loadTemplate(e.currentTarget.value)} class="template-select">
        <option value="">불러오기...</option>
        {#each templateList as t}<option value={t.name}>{t.name}</option>{/each}
      </select>
      <button class="btn" on:click={handleSave}>템플릿 저장</button>
      <button class="btn" on:click={clearTemplate}>새 템플릿</button>
      <button class="btn" on:click={triggerFileInput}>템플릿 열기</button>
      <button class="btn" on:click={downloadTemplate}>템플릿 다운로드</button>
      <button class="btn" on:click={() => showImportModal = true}>프리셋 가져오기</button>
      <span class="status">{status}</span>
    </div>
  </header>

  <!-- Main -->
  <div class="body">
    <!-- Left: Variable list -->
    <aside class="var-list">
      <div class="section-head">변수 ({$template.variables.length})</div>
      <div class="add-row">
        <input bind:value={newVariableName} placeholder="새 변수 이름" on:keydown={(e) => e.key === "Enter" && addVariable()} />
        <button class="btn sm" on:click={addVariable}>추가</button>
      </div>
      <ul class="items">
        {#each $template.variables as variable, idx}
          <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-noninteractive-element-interactions -->
          <li class:active={selectedVarIndex === idx} on:click={() => { selectedVarIndex = idx; selectedValIndex = null; }}>
            <span class="nm">{variable.name}</span>
            <span class="cnt">{variable.values.length}개</span>
            <button class="del" on:click|stopPropagation={() => deleteVariable(idx)}>×</button>
          </li>
        {:else}
          <li class="empty">변수 없음</li>
        {/each}
      </ul>
    </aside>

    <!-- Right: Value grid -->
    <main class="val-grid">
      {#if selectedVar}
        <div class="section-head">"{selectedVar.name}" 값 ({selectedVar.values.length})</div>
        <div class="add-row">
          <input bind:value={newValueName} placeholder="값 이름" />
          <input bind:value={newValueTags} placeholder="태그 (쉼표 구분)" class="tags-input" />
          <button class="btn sm" on:click={addValue}>추가</button>
        </div>
        <div class="values">
          {#each selectedVar.values as value, idx}
            <button type="button" class="value-card" class:active={selectedValIndex === idx}
              on:click={() => selectedVarIndex !== null && selectValue(selectedVarIndex, idx)}>
              <div class="val-head">
                <span class="val-name">{value.name}</span>
                <span class="del-btn" on:click|stopPropagation={() => selectedVarIndex !== null && deleteValue(selectedVarIndex, idx)} role="button" tabindex="-1">×</span>
              </div>
              <div class="val-tags">{value.tags.join(", ") || "(태그 없음)"}</div>
            </button>
          {:else}
            <div class="empty-vals">값을 추가하세요</div>
          {/each}
        </div>
      {:else}
        <div class="placeholder">
          <div class="icon">📋</div>
          <div>좌측에서 변수를 선택하세요</div>
        </div>
      {/if}
    </main>
  </div>

  <!-- Bottom Panel -->
  <div class="bottom-panel">
    <div class="bottom-header">태그 편집</div>
    <div class="bottom-content">
        {#if editingValue}
          <div class="tag-edit-row">
            <div class="te-field">
              <span class="lbl">값 이름</span>
              <input bind:value={editName} />
            </div>
            <div class="te-field wide">
              <span class="lbl">태그 (쉼표 구분)</span>
              <textarea bind:value={editTags} rows="2" placeholder="tag1, tag2, tag3, ..."></textarea>
            </div>
            <div class="te-actions">
              <button class="btn primary" on:click={saveEditValue}>저장</button>
            </div>
          </div>
        {:else}
          <div class="empty-msg">값을 선택하면 태그를 편집할 수 있습니다</div>
        {/if}
        
        <!-- 태그 일괄 작업 -->
        <div class="bulk-section">
          <div class="bulk-row">
            <button class="btn sm" on:click={removeCommonTags} disabled={selectedVarIndex === null}>공통 태그 제외</button>
            <div class="inline-input">
              <input bind:value={bulkTagRemove} placeholder="삭제할 태그들 (쉼표 구분)" />
              <button class="btn sm" on:click={removeTagsFromAll} disabled={selectedVarIndex === null}>모든 값에서 삭제</button>
            </div>
          </div>
          <!-- 값 이름 일괄 변경 -->
          <div class="bulk-row">
            <span class="bulk-label">값 이름 일괄:</span>
            <input bind:value={bulkPrefix} placeholder="앞에 추가" class="mini" />
            <button class="btn sm" on:click={applyBulkPrefix} disabled={selectedVarIndex === null}>적용</button>
            <input bind:value={bulkSuffix} placeholder="뒤에 추가" class="mini" />
            <button class="btn sm" on:click={applyBulkSuffix} disabled={selectedVarIndex === null}>적용</button>
            <input bind:value={bulkFind} placeholder="찾기" class="mini" />
            <input bind:value={bulkReplace} placeholder="바꾸기" class="mini" />
            <button class="btn sm" on:click={applyBulkReplace} disabled={selectedVarIndex === null}>적용</button>
            <input bind:value={bulkRemove} placeholder="삭제" class="mini" />
            <button class="btn sm" on:click={applyBulkRemove} disabled={selectedVarIndex === null}>적용</button>
          </div>
        </div>
    </div>
  </div>

  <!-- Preset Import Modal -->
  {#if showImportModal}
    <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
    <div class="modal-overlay" on:click={() => showImportModal = false}>
      <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
      <div class="modal wide" on:click|stopPropagation>
        <div class="modal-head">
          <span>프리셋 가져오기</span>
          <button on:click={() => showImportModal = false}>×</button>
        </div>
        <div class="modal-tabs">
          <button class:active={importTab === "file"} on:click={() => importTab = "file"}>SD Studio / NAIS에서</button>
          <button class:active={importTab === "folder"} on:click={() => importTab = "folder"}>이미지 폴더에서</button>
        </div>
        <div class="modal-body">
          {#if importTab === "file"}
            <p class="desc">NAI Style (.nai) 또는 SD Studio 형식의 프리셋 파일을 선택하세요.</p>
            <div class="field">
              <span class="lbl">대상 변수명 (선택)</span>
              <input bind:value={importTargetVar} placeholder="비우면 파일명 사용" />
            </div>
            <div class="field">
              <button class="btn primary" on:click={triggerPresetFileInput}>파일 선택...</button>
            </div>
          {:else}
            <p class="desc">이미지 폴더를 분석하여 파일명에서 프리셋 값을 생성합니다.</p>
            <div class="field">
              <span class="lbl">이미지 폴더 경로</span>
              <div class="input-row">
                <input bind:value={buildFolder} placeholder="폴더 경로" />
                <button class="btn sm" on:click={triggerBuildFolderSelect}>찾기</button>
              </div>
            </div>
            <div class="field">
              <label class="checkbox">
                <input type="checkbox" bind:checked={buildIncludeNegative} />
                네거티브 태그 포함
              </label>
            </div>
            <div class="field">
              <span class="lbl">대상 변수</span>
              <select bind:value={buildTargetVar}>
                <option value="__new__">새 변수 생성</option>
                {#each $template.variables as v}<option value={v.name}>{v.name}</option>{/each}
              </select>
              {#if buildTargetVar === "__new__"}
                <input bind:value={buildNewVarName} placeholder="새 변수 이름" style="margin-top:4px" />
              {/if}
            </div>
            <div class="field">
              <span class="lbl">모드</span>
              <div class="radio-group">
                <label class="radio"><input type="radio" bind:group={buildMode} value="replace" /> 덮어쓰기</label>
                <label class="radio"><input type="radio" bind:group={buildMode} value="append" /> 추가</label>
              </div>
            </div>
            <div class="field">
              <button class="btn primary" on:click={handleBuildAndClose}>프리셋 만들기</button>
            </div>
            {#if buildCommonTags.length > 0}
              <div class="common-tags-box">
                <span class="lbl">공통 태그:</span> {buildCommonTags.slice(0, 20).join(", ")}{buildCommonTags.length > 20 ? "..." : ""}
              </div>
            {/if}
          {/if}
          {#if importStatus || buildStatus}<div class="status">{importStatus || buildStatus}</div>{/if}
        </div>
        <div class="modal-foot">
          <button class="btn" on:click={() => showImportModal = false}>닫기</button>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
.editor{display:flex;flex-direction:column;height:100%;gap:8px}
.header{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;background:var(--panel);border-radius:var(--radius);flex-wrap:wrap;gap:10px}
.name-area{display:flex;align-items:center;gap:10px}
.template-name{font-size:15px;font-weight:600;padding:5px 10px;background:var(--bg);border:1px solid rgba(255,255,255,0.08);border-radius:6px;color:var(--text);min-width:180px}
.count{font-size:11px;color:var(--text-muted)}
.actions{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.template-select{padding:5px 8px;background:var(--bg);border:1px solid rgba(255,255,255,0.08);border-radius:6px;color:var(--text);font-size:11px;min-width:100px}
.btn{padding:5px 10px;background:var(--panel-2);border:none;border-radius:6px;color:var(--text);font-size:11px;font-weight:600;cursor:pointer;white-space:nowrap}
.btn:hover{background:var(--bg)}
.btn:disabled{opacity:0.4;cursor:not-allowed}
.btn.sm{padding:4px 8px;font-size:10px}
.btn.primary{background:var(--accent);color:var(--bg)}
.status{font-size:10px;color:var(--accent)}

.body{display:flex;flex:1 1 0;gap:8px;min-height:0;height:0;overflow:hidden}
.var-list{width:180px;background:var(--panel);border-radius:var(--radius);display:flex;flex-direction:column;flex-shrink:0;min-height:0;height:100%;overflow:hidden}
.section-head{padding:10px 12px;font-weight:600;font-size:12px;border-bottom:1px solid rgba(255,255,255,0.06)}
.add-row{display:flex;gap:4px;padding:6px}
.add-row input{flex:1;padding:5px 6px;background:var(--bg);border:1px solid rgba(255,255,255,0.08);border-radius:4px;color:var(--text);font-size:10px;min-width:0}
.add-row .tags-input{flex:2}
.items{flex:1 1 0;overflow-y:auto;list-style:none;margin:0;padding:4px;height:0}
.items li{display:flex;align-items:center;gap:4px;padding:6px 8px;border-radius:5px;cursor:pointer;font-size:11px}
.items li:hover{background:var(--bg)}
.items li.active{background:var(--accent);color:var(--bg)}
.items li .nm{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.items li .cnt{font-size:9px;opacity:0.7}
.items li .del{background:none;border:none;color:inherit;opacity:0.4;cursor:pointer;font-size:13px;padding:2px}
.items li .del:hover{opacity:1}
.items li.empty{justify-content:center;color:var(--text-muted);cursor:default}

.val-grid{flex:1;background:var(--panel);border-radius:var(--radius);display:flex;flex-direction:column;min-height:0;height:100%;overflow:hidden}
.values{flex:1 1 0;overflow-y:auto;padding:6px;display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:6px;align-content:start;height:0}
.value-card{background:var(--bg);border-radius:6px;padding:8px 10px;cursor:pointer;border:2px solid transparent;transition:border-color 0.15s;text-align:left;width:100%;font-family:inherit}
.value-card:hover{border-color:var(--accent)}
.value-card.active{border-color:var(--accent);background:rgba(52,211,153,0.1)}
.val-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
.val-name{font-weight:600;font-size:12px}
.val-tags{font-size:10px;color:var(--text-muted);line-height:1.3;max-height:48px;overflow:hidden;word-break:break-word}
.del-btn{background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:13px}
.del-btn:hover{color:var(--danger)}
.empty-vals{grid-column:1/-1;text-align:center;padding:30px;color:var(--text-muted);font-size:12px}
.placeholder{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:6px;color:var(--text-muted)}
.placeholder .icon{font-size:40px;opacity:0.3}

/* Bottom Panel */
.bottom-panel{background:var(--panel);border-radius:var(--radius);flex-shrink:0}
.bottom-header{padding:8px 12px;font-weight:600;font-size:11px;border-bottom:1px solid rgba(255,255,255,0.06);color:var(--text-muted)}
.bottom-content{padding:10px 12px}

/* Tag edit row */
.tag-edit-row{display:flex;gap:12px;align-items:flex-start;margin-bottom:10px}
.te-field{display:flex;flex-direction:column;gap:3px}
.te-field.wide{flex:1}
.te-field .lbl{font-size:10px;color:var(--text-muted)}
.te-field input,.te-field textarea{padding:6px 8px;background:var(--bg);border:1px solid rgba(255,255,255,0.08);border-radius:5px;color:var(--text);font-size:11px;font-family:inherit;resize:vertical}
.te-field textarea{min-height:40px}
.te-actions{display:flex;align-items:flex-end;padding-bottom:2px}
.empty-msg{color:var(--text-muted);font-size:11px;padding:8px 0}

/* Bulk section */
.bulk-section{display:flex;flex-direction:column;gap:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.04)}
.bulk-row{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.bulk-label{font-size:10px;color:var(--text-muted);flex-shrink:0}
.inline-input{display:flex;gap:4px;flex:1}
.inline-input input{flex:1;padding:5px 8px;background:var(--bg);border:1px solid rgba(255,255,255,0.08);border-radius:4px;color:var(--text);font-size:10px}
input.mini{width:70px;padding:4px 6px;background:var(--bg);border:1px solid rgba(255,255,255,0.08);border-radius:4px;color:var(--text);font-size:10px}



/* Modal */
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;z-index:200}
.modal{background:var(--panel);border-radius:var(--radius);width:360px;max-width:90vw}
.modal.wide{width:480px}
.modal-head{display:flex;justify-content:space-between;align-items:center;padding:12px 14px;border-bottom:1px solid rgba(255,255,255,0.06);font-weight:600;font-size:13px}
.modal-head button{background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:16px}
.modal-tabs{display:flex;border-bottom:1px solid rgba(255,255,255,0.06)}
.modal-tabs button{flex:1;padding:10px 12px;background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:11px;font-weight:600}
.modal-tabs button:hover{background:var(--bg)}
.modal-tabs button.active{color:var(--accent);border-bottom:2px solid var(--accent)}
.modal-body{padding:14px}
.modal-body .desc{font-size:11px;color:var(--text-muted);margin-bottom:12px}
.modal-body .field{display:flex;flex-direction:column;gap:4px;margin-bottom:10px}
.modal-body .field .lbl{font-size:10px;color:var(--text-muted)}
.modal-body .field input,.modal-body .field select{padding:6px 8px;background:var(--bg);border:1px solid rgba(255,255,255,0.08);border-radius:5px;color:var(--text);font-size:11px}
.modal-body .field .input-row{display:flex;gap:4px}
.modal-body .field .input-row input{flex:1}
.modal-body .field .checkbox,.modal-body .field .radio{display:flex;align-items:center;gap:5px;font-size:11px;cursor:pointer}
.modal-body .field .radio-group{display:flex;gap:12px}
.modal-body .status{font-size:10px;color:var(--accent);margin-top:8px}
.modal-body .common-tags-box{font-size:10px;color:var(--text-muted);margin-top:8px;padding:8px;background:var(--bg);border-radius:5px}
.modal-body .common-tags-box .lbl{color:var(--text)}
.modal-foot{display:flex;justify-content:flex-end;gap:6px;padding:10px 14px;border-top:1px solid rgba(255,255,255,0.06)}
</style>
