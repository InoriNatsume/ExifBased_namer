// Svelte stores for state management

import { writable } from "svelte/store";
import type { ResultRecord, ResultStatus } from "./types";

// Current active tab
export const activeTab = writable<"editor" | "rename" | "move">("rename");

// Job state
export interface JobState {
  active: boolean;
  jobId: string | null;
  op: string | null;
  processed: number;
  total: number;
  errors: number;
  skipped: number;
  status: string;
}

export const jobState = writable<JobState>({
  active: false,
  jobId: null,
  op: null,
  processed: 0,
  total: 0,
  errors: 0,
  skipped: 0,
  status: "대기",
});

// Results
export const results = writable<ResultRecord[]>([]);

// Result stats
export interface ResultStats {
  ok: number;
  unknown: number;
  conflict: number;
  error: number;
  skip: number;
}

export const resultStats = writable<ResultStats>({
  ok: 0,
  unknown: 0,
  conflict: 0,
  error: 0,
  skip: 0,
});

// Filter visibility
export const filters = writable<Record<ResultStatus, boolean>>({
  OK: true,
  UNKNOWN: true,
  CONFLICT: true,
  ERROR: true,
  SKIP: true,
});

// Template state
export interface TemplateVariable {
  name: string;
  values: Array<{ name: string; tags: string[] }>;
}

export interface Template {
  name: string | null;
  variables: TemplateVariable[];
}

export const template = writable<Template>({
  name: null,
  variables: [],
});

// Logs
export const logs = writable<string[]>([]);

export function appendLog(message: string) {
  logs.update((items) => [message, ...items].slice(0, 100));
}

// Helper to reset job state
export function resetJob(op: string, jobId: string) {
  jobState.set({
    active: true,
    jobId,
    op,
    processed: 0,
    total: 0,
    errors: 0,
    skipped: 0,
    status: "진행 중",
  });
  results.set([]);
  resultStats.set({ ok: 0, unknown: 0, conflict: 0, error: 0, skip: 0 });
}

// Helper to add a result
export function addResult(record: ResultRecord) {
  results.update((items) => [...items, record]);
  resultStats.update((stats) => {
    const key = record.status.toLowerCase() as keyof ResultStats;
    return { ...stats, [key]: stats[key] + 1 };
  });
}
