// WebSocket client for job updates

import type { IpcMessage } from "./types";

export type MessageHandler = (message: IpcMessage) => void;

// In development, API is on :8000
const WS_HOST = import.meta.env.DEV ? "localhost:8000" : window.location.host;

/**
 * Connect to a job's WebSocket and receive updates
 */
export function connectJob(
  jobId: string,
  onMessage: MessageHandler,
  onClose?: () => void
): { close: () => void } {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${WS_HOST}/ws/job/${jobId}`;
  
  const ws = new WebSocket(wsUrl);
  
  ws.onopen = () => {
    console.log(`[WS] Connected to job ${jobId}`);
  };
  
  ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data) as IpcMessage;
      if (message.type !== "ping") {
        onMessage(message);
      }
    } catch (err) {
      console.error("[WS] Failed to parse message:", err);
    }
  };
  
  ws.onerror = (err) => {
    console.error("[WS] Error:", err);
  };
  
  ws.onclose = () => {
    console.log(`[WS] Disconnected from job ${jobId}`);
    onClose?.();
  };
  
  return {
    close: () => ws.close(),
  };
}

/**
 * Helper to run a job and collect all messages
 */
export async function runJobWithUpdates(
  jobId: string,
  onProgress?: (processed: number, total: number) => void,
  onResult?: (result: IpcMessage) => void
): Promise<IpcMessage[]> {
  return new Promise((resolve, reject) => {
    const messages: IpcMessage[] = [];
    
    const conn = connectJob(
      jobId,
      (message) => {
        messages.push(message);
        
        if (message.type === "progress" && onProgress) {
          onProgress(message.processed, message.total);
        }
        
        if (message.type === "result" && onResult) {
          onResult(message);
        }
        
        if (message.type === "done") {
          conn.close();
          resolve(messages);
        }
        
        if (message.type === "error") {
          conn.close();
          reject(new Error(message.message));
        }
      },
      () => {
        resolve(messages);
      }
    );
  });
}
