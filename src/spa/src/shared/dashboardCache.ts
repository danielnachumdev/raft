import {
  fetchStatus,
  type MetricsPayload,
  type StatusPayload,
} from "./api";

/** Ignore sessionStorage entries older than this (hard refresh within tab). */
export const CACHE_TTL_MS = 10 * 60 * 1000;

const STATUS_KEY = "raft.serve.status.v1";
const METRICS_KEY_PREFIX = "raft.serve.metrics.v1.";

type Entry<T> = { fetchedAt: number; payload: T };

let statusMemory: Entry<StatusPayload> | null = null;
const metricsMemory = new Map<string, Entry<MetricsPayload>>();

/** Fresh cached status, or null if missing/stale. */
export function peekStatus(): StatusPayload | null {
  if (statusMemory && !expired(statusMemory.fetchedAt)) {
    return statusMemory.payload;
  }
  const fromSession = readSession<StatusPayload>(STATUS_KEY);
  if (!fromSession) {
    statusMemory = null;
    return null;
  }
  statusMemory = fromSession;
  return fromSession.payload;
}

export function putStatus(payload: StatusPayload): void {
  statusMemory = { fetchedAt: Date.now(), payload };
  writeSession(STATUS_KEY, statusMemory);
}

/** Drop status so the next dashboard visit refetches (after mutative actions). */
export function invalidateStatus(): void {
  statusMemory = null;
  removeSession(STATUS_KEY);
}

/** Fetch status, store it, and return the payload. */
export async function refreshStatus(): Promise<StatusPayload> {
  const payload = await fetchStatus();
  putStatus(payload);
  return payload;
}

/** Fresh cached full metrics for a query key, or null. */
export function peekMetrics(cacheKey: string): MetricsPayload | null {
  const mem = metricsMemory.get(cacheKey);
  if (mem && !expired(mem.fetchedAt)) return mem.payload;
  const fromSession = readSession<MetricsPayload>(metricsKey(cacheKey));
  if (!fromSession) {
    metricsMemory.delete(cacheKey);
    return null;
  }
  metricsMemory.set(cacheKey, fromSession);
  return fromSession.payload;
}

export function putMetrics(cacheKey: string, payload: MetricsPayload): void {
  const entry: Entry<MetricsPayload> = { fetchedAt: Date.now(), payload };
  metricsMemory.set(cacheKey, entry);
  writeSession(metricsKey(cacheKey), entry);
}

export function invalidateMetrics(): void {
  metricsMemory.clear();
  if (typeof sessionStorage === "undefined") return;
  const doomed: string[] = [];
  for (let i = 0; i < sessionStorage.length; i += 1) {
    const key = sessionStorage.key(i);
    if (key && key.startsWith(METRICS_KEY_PREFIX)) doomed.push(key);
  }
  for (const key of doomed) sessionStorage.removeItem(key);
}

function metricsKey(cacheKey: string): string {
  return `${METRICS_KEY_PREFIX}${cacheKey}`;
}

function expired(fetchedAt: number): boolean {
  return Date.now() - fetchedAt > CACHE_TTL_MS;
}

function readSession<T>(key: string): Entry<T> | null {
  if (typeof sessionStorage === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Entry<T>;
    if (
      !parsed ||
      typeof parsed.fetchedAt !== "number" ||
      parsed.payload === undefined ||
      expired(parsed.fetchedAt)
    ) {
      sessionStorage.removeItem(key);
      return null;
    }
    return parsed;
  } catch {
    sessionStorage.removeItem(key);
    return null;
  }
}

function writeSession<T>(key: string, entry: Entry<T>): void {
  if (typeof sessionStorage === "undefined") return;
  try {
    sessionStorage.setItem(key, JSON.stringify(entry));
  } catch {
    /* quota / private mode — memory cache still works */
  }
}

function removeSession(key: string): void {
  if (typeof sessionStorage === "undefined") return;
  sessionStorage.removeItem(key);
}
