// IPC Message types (shared with server)

export interface IpcProgress {
  id: string;
  type: "progress";
  processed: number;
  total: number;
  errors: number;
  skipped?: number;
}

export interface IpcResult {
  id: string;
  type: "result";
  status: "OK" | "UNKNOWN" | "CONFLICT" | "ERROR" | "SKIP";
  source: string;
  target?: string;
  message?: string;
  preview?: string;
}

export interface IpcDone {
  id: string;
  type: "done";
  processed?: number;
  errors?: number;
  skipped?: number;
  cancelled?: boolean;
  completed?: boolean;
  stats?: Record<string, unknown>;
  payload?: unknown;
}

export interface IpcError {
  id: string;
  type: "error";
  message: string;
}

export interface IpcLog {
  id?: string;
  type: "log";
  message: string;
}

export interface IpcAck {
  id: string;
  type: "ack";
  op: string;
}

export interface IpcPing {
  type: "ping";
}

export type IpcMessage =
  | IpcProgress
  | IpcResult
  | IpcDone
  | IpcError
  | IpcLog
  | IpcAck
  | IpcPing;

export type ResultStatus = "OK" | "UNKNOWN" | "CONFLICT" | "ERROR" | "SKIP";

export interface ResultRecord {
  status: ResultStatus;
  source: string;
  target?: string;
  message?: string;
  preview?: string;
}
