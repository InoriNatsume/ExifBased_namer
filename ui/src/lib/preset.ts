export type PresetValue = {
  name: string;
  tags: string[];
};

export type PresetVariable = {
  name: string;
  values: PresetValue[];
};

export type Preset = {
  name: string;
  variables: PresetVariable[];
};

export type ConflictSummary = {
  duplicates: [string, string][];
  subsets: [string, string][];
};

export function normalizeTagText(text: string): string[] {
  return text
    .split(",")
    .map((tag) => tag.trim())
    .filter((tag) => tag.length > 0);
}

export function normalizeTags(tags: string[]): string[] {
  const seen = new Set<string>();
  const output: string[] = [];
  for (const tag of tags) {
    const trimmed = tag.trim();
    if (!trimmed || seen.has(trimmed)) {
      continue;
    }
    seen.add(trimmed);
    output.push(trimmed);
  }
  return output;
}

export function tagsKey(tags: string[]): string {
  return [...tags].sort().join("||");
}

export function detectConflicts(values: PresetValue[]): ConflictSummary {
  const duplicates: [string, string][] = [];
  const subsets: [string, string][] = [];
  const keys = values.map((value) => tagsKey(value.tags));
  const tagSets = values.map((value) => new Set(value.tags));

  for (let i = 0; i < values.length; i += 1) {
    for (let j = i + 1; j < values.length; j += 1) {
      if (keys[i] === keys[j]) {
        duplicates.push([values[i].name, values[j].name]);
        continue;
      }
      if (isSubset(tagSets[i], tagSets[j])) {
        subsets.push([values[i].name, values[j].name]);
      } else if (isSubset(tagSets[j], tagSets[i])) {
        subsets.push([values[j].name, values[i].name]);
      }
    }
  }

  return { duplicates, subsets };
}

export function removeCommonTags(values: PresetValue[]): {
  values: PresetValue[];
  common: string[];
} {
  if (values.length === 0) {
    return { values, common: [] };
  }
  const common = new Set(values[0].tags);
  for (const value of values.slice(1)) {
    for (const tag of [...common]) {
      if (!value.tags.includes(tag)) {
        common.delete(tag);
      }
    }
  }
  const commonList = [...common];
  const updated = values.map((value) => ({
    ...value,
    tags: value.tags.filter((tag) => !common.has(tag)),
  }));
  return { values: updated, common: commonList };
}

function isSubset(source: Set<string>, target: Set<string>): boolean {
  for (const item of source) {
    if (!target.has(item)) {
      return false;
    }
  }
  return true;
}
