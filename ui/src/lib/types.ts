type IpcBase = {
  id?: string;
  version?: number;
};

export type IpcRunRequest = {
  id: string;
  type: "run";
  op: string;
  payload: Record<string, unknown>;
  version?: number;
};

export type IpcCancelRequest = {
  id: string;
  type: "cancel";
  version?: number;
};

export type IpcMessage =
  | (IpcBase & { type: "ack"; op?: string })
  | (IpcBase & {
      type: "progress";
      processed?: number;
      total?: number;
      errors?: number;
      skipped?: number;
    })
  | (IpcBase & {
      type: "result";
      status?: string;
      source?: string;
      target?: string;
      message?: string;
      preview?: string;
    })
  | (IpcBase & {
      type: "done";
      processed?: number;
      errors?: number;
      skipped?: number;
      matches?: number;
      cancelled?: boolean;
      payload?: unknown;
      stats?: Record<string, unknown>;
    })
  | (IpcBase & { type: "log"; message?: string })
  | (IpcBase & { type: "error"; message?: string });
