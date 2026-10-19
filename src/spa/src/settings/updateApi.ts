/** Typed client for serve ``/api/update`` (check + apply). */

import { detailFromBody, readJsonBody } from "../shared/api/http";

export type UpdateStatus = {
  current: string;
  currentLine: string;
  latestTag: string | null;
  latestVersion: string | null;
  updateAvailable: boolean;
  releaseUrl: string | null;
  state: "up_to_date" | "update_available" | "ahead" | "unknown" | string;
  message: string;
};

export type UpdateApplyResult = {
  alreadyCurrent: boolean;
  beforeLine: string | null;
  afterLine: string | null;
  nextSteps: string | null;
};

async function jsonRequest<T>(
  url: string,
  init?: RequestInit,
  label = "request",
): Promise<T> {
  const res = await fetch(url, init);
  const body = await readJsonBody(res);
  if (!res.ok) {
    throw new Error(detailFromBody(body) || `${label} ${res.status}`);
  }
  return body as T;
}

export async function fetchUpdateStatus(): Promise<UpdateStatus> {
  return jsonRequest<UpdateStatus>("/api/update/status", undefined, "update status");
}

export async function applyUpdate(ref?: string): Promise<UpdateApplyResult> {
  const init: RequestInit = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(ref ? { ref } : {}),
  };
  return jsonRequest<UpdateApplyResult>("/api/update", init, "update");
}
