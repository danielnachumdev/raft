import type { DeployJob } from "../github/types.ts";

const STORAGE_KEY = "raft-serve-github-deploy-job";

type StoredDeployJob = {
  id: string;
  full_name: string;
  ref: string;
  manifest_path: string;
};

/** Remember the in-flight deploy so leaving /deploy can resume polling. */
export function persistDeployJob(job: DeployJob): void {
  if (typeof sessionStorage === "undefined") return;
  const payload: StoredDeployJob = {
    id: job.id,
    full_name: job.full_name,
    ref: job.ref,
    manifest_path: job.manifest_path || ".raft/app.yaml",
  };
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

export function clearPersistedDeployJob(): void {
  if (typeof sessionStorage === "undefined") return;
  sessionStorage.removeItem(STORAGE_KEY);
}

export function readPersistedDeployJobId(): string | null {
  if (typeof sessionStorage === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredDeployJob;
    return typeof parsed.id === "string" && parsed.id ? parsed.id : null;
  } catch {
    return null;
  }
}

export function isDeployInFlight(job: DeployJob | null): boolean {
  return Boolean(job && (job.status === "pending" || job.status === "running"));
}
