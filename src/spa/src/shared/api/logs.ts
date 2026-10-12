/** Service log snapshot + SSE follow helpers. */

import { detailFromBody, readJsonBody } from "./http.ts";

export type ServiceLogsPayload = {
  service: string;
  tail: number;
  text: string;
};

export const DEFAULT_LOG_TAIL = 100;

export function serviceLogsFollowUrl(
  name: string,
  tail: number = DEFAULT_LOG_TAIL,
): string {
  const params = new URLSearchParams();
  params.set("tail", String(tail));
  return `/api/service/${encodeURIComponent(name)}/logs/follow?${params.toString()}`;
}

export async function fetchServiceLogs(
  name: string,
  tail: number = DEFAULT_LOG_TAIL,
): Promise<ServiceLogsPayload> {
  const params = new URLSearchParams();
  params.set("tail", String(tail));
  const res = await fetch(
    `/api/service/${encodeURIComponent(name)}/logs?${params.toString()}`,
  );
  const body = await readJsonBody(res);
  if (!res.ok) {
    throw new Error(detailFromBody(body) || `logs failed (${res.status})`);
  }
  return body as ServiceLogsPayload;
}

/** Open SSE follow stream; resolves once the response is ready. */
export async function openServiceLogsFollow(
  name: string,
  tail: number,
  signal: AbortSignal,
): Promise<AsyncGenerator<string, void, void>> {
  const res = await fetch(serviceLogsFollowUrl(name, tail), { signal });
  if (!res.ok) {
    const body = await readJsonBody(res);
    throw new Error(detailFromBody(body) || `logs follow failed (${res.status})`);
  }
  if (!res.body) {
    throw new Error("logs follow failed (empty body)");
  }
  return readSseDataLines(res.body, signal);
}

async function* readSseDataLines(
  body: ReadableStream<Uint8Array>,
  signal: AbortSignal,
): AsyncGenerator<string, void, void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (!signal.aborted) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const chunk of parts) {
        const line = sseDataPayload(chunk);
        if (line !== null) yield line;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function sseDataPayload(chunk: string): string | null {
  const lines = chunk.split("\n");
  const data: string[] = [];
  for (const line of lines) {
    if (line.startsWith("data:")) {
      data.push(line.slice(5).replace(/^ /, ""));
    }
  }
  if (data.length === 0) return null;
  return data.join("\n");
}
