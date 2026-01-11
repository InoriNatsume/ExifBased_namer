export type ResultStatus = "OK" | "UNKNOWN" | "CONFLICT" | "ERROR" | "SKIP";

export type ResultRecord = {
  id: string;
  status: ResultStatus;
  text: string;
  source?: string;
  target?: string;
  preview?: string;
};

export type JobMode = "search" | "scan" | "rename" | "move" | "strip" | "build_nais";

export type JobProgress = {
  processed: number;
  total: number;
  errors: number;
  skipped: number;
  startedAt: number;
};

export type JobStats = {
  ok: number;
  unknown: number;
  conflict: number;
  error: number;
  skipped: number;
};

export function formatEta(progress: JobProgress): string {
  if (!progress.total || progress.processed <= 0) {
    return "00:00:00";
  }
  const elapsed = (Date.now() - progress.startedAt) / 1000;
  if (elapsed <= 0) {
    return "00:00:00";
  }
  const rate = progress.processed / elapsed;
  if (rate <= 0) {
    return "00:00:00";
  }
  const remaining = Math.max(0, progress.total - progress.processed);
  const seconds = Math.round(remaining / rate);
  const hh = String(Math.floor(seconds / 3600)).padStart(2, "0");
  const mm = String(Math.floor((seconds % 3600) / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}
