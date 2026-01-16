// API client for NAI Tag Classifier server

// In development, Vite runs on :5173 but API is on :8000
const API_BASE = import.meta.env.DEV ? "http://localhost:8000" : "";

export interface JobResponse {
  job_id: string;
  status: string;
}

export interface SimpleResponse {
  results?: unknown[];
  error?: string;
}

/**
 * Create a new job (async, use WebSocket to get updates)
 */
export async function createJob(
  op: string,
  payload: Record<string, unknown> = {}
): Promise<JobResponse> {
  const res = await fetch(`${API_BASE}/api/job`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ op, payload }),
  });
  return res.json();
}

/**
 * Cancel a running job
 */
export async function cancelJob(jobId: string): Promise<void> {
  await fetch(`${API_BASE}/api/job/${jobId}/cancel`, {
    method: "POST",
  });
}

/**
 * Run a simple job synchronously (for quick operations)
 */
export async function runSimpleJob<T = unknown>(
  op: string,
  payload: Record<string, unknown> = {}
): Promise<T> {
  const res = await fetch(`${API_BASE}/api/simple/${op}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (data.error) {
    throw new Error(data.error);
  }
  // Extract the done message payload
  const doneMsg = data.results?.find((r: { type: string }) => r.type === "done");
  return doneMsg || data;
}

// ============ File System APIs ============

export interface BrowseItem {
  name: string;
  type: "folder" | "file" | "drive";
  path: string;
}

export interface BrowseResult {
  current: string;
  parent: string | null;
  items: BrowseItem[];
}

/**
 * Browse folder on server
 */
export async function browseFolder(path: string = ""): Promise<BrowseResult> {
  const res = await fetch(`${API_BASE}/api/browse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  return res.json();
}

/**
 * Open native folder selection dialog (via server tkinter)
 */
export async function selectFolder(): Promise<string | null> {
  const res = await fetch(`${API_BASE}/api/select-folder`);
  const data = await res.json();
  return data.path || null;
}

/**
 * Get thumbnail URL for an image
 */
export function getThumbnailUrl(imagePath: string): string {
  return `${API_BASE}/api/thumbs/${encodeURIComponent(imagePath)}`;
}

/**
 * Get DB stats
 */
export async function getDbStats(): Promise<{
  images: number;
  tags: number;
  matches: number;
}> {
  const result = await runSimpleJob<{ stats: { images: number; tags: number; matches: number } }>(
    "db_stats"
  );
  return result.stats;
}

/**
 * List templates from DB
 */
export async function listTemplates(): Promise<
  Array<{ id: number; name: string; created_at: string; updated_at: string }>
> {
  const result = await runSimpleJob<{ payload: { templates: unknown[] } }>(
    "template_db_list"
  );
  return (result.payload?.templates as Array<{ id: number; name: string; created_at: string; updated_at: string }>) || [];
}

/**
 * Get a template by name
 */
export async function getTemplate(name: string): Promise<{ name: string; variables: unknown[] } | null> {
  const result = await runSimpleJob<{ payload: { id: number; name: string; payload: { name?: string; variables: unknown[] }; updated_at: string } }>(
    "template_db_get",
    { name }
  );
  // DB stores: { id, name, payload: { name, variables }, updated_at }
  // We need to return { name, variables } for the store
  const templateData = result.payload;
  if (!templateData) return null;
  return {
    name: templateData.name,
    variables: templateData.payload?.variables || [],
  };
}

/**
 * Save a template
 */
export async function saveTemplate(
  name: string,
  template: unknown
): Promise<void> {
  await runSimpleJob("template_db_save", { name, template });
}

/**
 * Delete a template
 */
export async function deleteTemplate(name: string): Promise<void> {
  await runSimpleJob("template_db_delete", { name });
}

// ============ Preset DB APIs ============

export interface PresetInfo {
  id: number;
  name: string;
  source_kind: string;
  variable_name: string;
  created_at: string;
  updated_at: string;
}

export interface PresetValue {
  name: string;
  tags: string[];
}

/**
 * List presets from DB (optionally filter by variable name)
 */
export async function listPresets(variableName?: string): Promise<PresetInfo[]> {
  const result = await runSimpleJob<{ payload: { presets: PresetInfo[] } }>(
    "preset_db_list",
    variableName ? { variable_name: variableName } : {}
  );
  return result.payload?.presets || [];
}

/**
 * Get a preset by ID
 */
export async function getPreset(id: number): Promise<{ preset: unknown; values: PresetValue[] }> {
  const result = await runSimpleJob<{ payload: { preset: unknown; values: PresetValue[] } }>(
    "preset_db_get",
    { id }
  );
  return result.payload || { preset: null, values: [] };
}

/**
 * Save a preset to DB
 */
export async function savePreset(payload: {
  name: string;
  source_kind: string;
  variable_name: string;
  values: PresetValue[];
}): Promise<void> {
  // Server expects {preset: {...}} format
  await runSimpleJob("preset_db_save", { preset: payload });
}

/**
 * Delete a preset from DB
 */
export async function deletePreset(id: number): Promise<void> {
  await runSimpleJob("preset_db_delete", { id });
}

// ============ File-based Preset APIs ============

/**
 * Load preset/template from file
 */
export async function loadPresetFile(path: string): Promise<unknown> {
  const result = await runSimpleJob<{ payload: { preset: unknown } }>(
    "preset_load",
    { path }
  );
  return result.payload?.preset;
}

/**
 * Save preset/template to file
 */
export async function savePresetFile(path: string, preset: unknown): Promise<void> {
  await runSimpleJob("preset_save", { path, preset });
}

/**
 * Import SDSTUDIO/NAIS preset file
 */
export async function importPresetFile(
  path: string,
  format?: string
): Promise<{ variable_name: string; values: PresetValue[] }> {
  const result = await runSimpleJob<{ payload: { variable_name: string; values: PresetValue[] } }>(
    "preset_import",
    { path, format }
  );
  return result.payload || { variable_name: "", values: [] };
}

// ============ Build APIs ============

export interface BuildResult {
  name: string;
  tags: string[];
}

/**
 * Build preset from folder (analyze images and extract tags)
 */
export async function buildFromFolder(payload: {
  folder: string;
  include_negative?: boolean;
  build_mode?: "intersection" | "union" | "difference";
}): Promise<BuildResult[]> {
  const result = await runSimpleJob<{ payload: { values: BuildResult[] } }>(
    "build_nais",
    payload
  );
  return result.payload?.values || [];
}

/**
 * Build preset from folder with common tags extraction
 */
export async function buildPresetFromFolder(
  folder: string,
  includeNegative: boolean = false
): Promise<{ values: PresetValue[]; common_tags: string[] }> {
  const result = await runSimpleJob<{ 
    payload: { 
      values: PresetValue[]; 
      common_tags?: string[];
      stats?: { common_count?: number }
    } 
  }>(
    "build_nais",
    { folder, include_negative: includeNegative }
  );
  return {
    values: result.payload?.values || [],
    common_tags: result.payload?.common_tags || []
  };
}

/**
 * Scan folder for images
 */
export async function scanFolder(folder: string): Promise<string[]> {
  const result = await runSimpleJob<{ payload: { files: string[] } }>(
    "scan",
    { folder }
  );
  return result.payload?.files || [];
}

// ============ Tag Analysis APIs ============

export interface TagConflict {
  tag: string;
  negative: string;
  values: string[];
}

/**
 * Find common tags across all values
 */
export function findCommonTags(values: PresetValue[]): string[] {
  if (values.length === 0) return [];
  
  const tagSets = values.map(v => new Set(v.tags));
  const firstSet = tagSets[0];
  
  return [...firstSet].filter(tag => 
    tagSets.every(set => set.has(tag))
  );
}

/**
 * Remove common tags from all values
 */
export function removeCommonTags(values: PresetValue[], commonTags: string[]): PresetValue[] {
  const commonSet = new Set(commonTags);
  return values.map(v => ({
    ...v,
    tags: v.tags.filter(t => !commonSet.has(t))
  }));
}

/**
 * Find tag conflicts (positive/negative pairs)
 */
export function findTagConflicts(values: PresetValue[]): TagConflict[] {
  const conflicts: TagConflict[] = [];
  const seen = new Map<string, { positive: Set<string>; negative: Set<string> }>();
  
  for (const value of values) {
    for (const tag of value.tags) {
      const isNegative = tag.startsWith("-");
      const baseTag = isNegative ? tag.slice(1) : tag;
      
      if (!seen.has(baseTag)) {
        seen.set(baseTag, { positive: new Set(), negative: new Set() });
      }
      
      const entry = seen.get(baseTag)!;
      if (isNegative) {
        entry.negative.add(value.name);
      } else {
        entry.positive.add(value.name);
      }
    }
  }
  
  for (const [baseTag, { positive, negative }] of seen) {
    if (positive.size > 0 && negative.size > 0) {
      conflicts.push({
        tag: baseTag,
        negative: `-${baseTag}`,
        values: [...positive, ...negative]
      });
    }
  }
  
  return conflicts;
}
