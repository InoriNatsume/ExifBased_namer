import { get } from "svelte/store";

import { normalizeTags, type PresetValue } from "./preset";
import { templateStore } from "./stores";

export function coerceValues(rawValues: unknown): PresetValue[] {
  if (!Array.isArray(rawValues)) {
    return [];
  }
  const values: PresetValue[] = [];
  for (const raw of rawValues) {
    if (!raw || typeof raw !== "object") {
      continue;
    }
    const name = String((raw as Record<string, unknown>).name ?? "").trim();
    if (!name) {
      continue;
    }
    const tagList = (raw as Record<string, unknown>).tags;
    const tags = Array.isArray(tagList)
      ? normalizeTags(tagList.map((tag) => String(tag)))
      : [];
    values.push({ name, tags });
  }
  return values;
}

function ensureUniqueValueName(name: string, existing: Set<string>): string {
  let candidate = name;
  let idx = 2;
  while (existing.has(candidate)) {
    candidate = `${name}_${idx}`;
    idx += 1;
  }
  existing.add(candidate);
  return candidate;
}

export function applyBuildValues(
  variableName: string,
  incoming: PresetValue[],
  mode: "replace" | "append"
): void {
  const template = get(templateStore);
  const variables = [...template.variables];
  const index = variables.findIndex((variable) => variable.name === variableName);
  if (index === -1) {
    variables.push({ name: variableName, values: incoming });
    templateStore.set({ ...template, variables });
    return;
  }

  if (mode === "replace") {
    variables[index] = { ...variables[index], values: incoming };
    templateStore.set({ ...template, variables });
    return;
  }

  const existingNames = new Set(variables[index].values.map((value) => value.name));
  const merged = [
    ...variables[index].values,
    ...incoming.map((value) => ({
      ...value,
      name: ensureUniqueValueName(value.name, existingNames),
    })),
  ];
  variables[index] = { ...variables[index], values: merged };
  templateStore.set({ ...template, variables });
}
