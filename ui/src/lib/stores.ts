import { writable } from "svelte/store";

import type { JobMode, JobProgress, JobStats, ResultRecord } from "./models";
import type { Preset } from "./preset";

export const logStore = writable<string[]>([]);
export const resultStore = writable<ResultRecord[]>([]);
export const templateStore = writable<Preset>({ name: "", variables: [] });

type JobState = {
  activeJob: JobMode | null;
  status: string;
  progressText: string;
  progress: JobProgress;
  stats: JobStats;
};

const initialProgress: JobProgress = {
  processed: 0,
  total: 0,
  errors: 0,
  skipped: 0,
  startedAt: Date.now(),
};

const initialStats: JobStats = {
  ok: 0,
  unknown: 0,
  conflict: 0,
  error: 0,
  skipped: 0,
};

export const jobStore = writable<JobState>({
  activeJob: null,
  status: "대기",
  progressText: "",
  progress: initialProgress,
  stats: initialStats,
});
