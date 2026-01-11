export type IpcRunRequest = {
  id: string;
  type: "run";
  op: string;
  payload: Record<string, unknown>;
};

export type IpcMessage =
  | { id?: string; type: "ack"; op?: string }
  | {
      id?: string;
      type: "progress";
      processed?: number;
      total?: number;
      errors?: number;
      skipped?: number;
    }
  | {
      id?: string;
      type: "result";
      status?: string;
      source?: string;
      target?: string;
      message?: string;
    }
  | {
      id?: string;
      type: "done";
      processed?: number;
      errors?: number;
      skipped?: number;
      matches?: number;
      cancelled?: boolean;
      payload?: unknown;
      stats?: Record<string, unknown>;
    }
  | { id?: string; type: "log"; message?: string }
  | { id?: string; type: "error"; message?: string };
