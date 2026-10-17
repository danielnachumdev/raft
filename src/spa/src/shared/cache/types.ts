/** Namespace + key identity for a cached resource (e.g. `firewall` / `document`). */
export type ResourceId = Readonly<{
  namespace: string;
  key: string;
}>;

export function resourceId(namespace: string, key: string): ResourceId {
  return { namespace, key };
}

export function resourceIdString(id: ResourceId): string {
  return `${id.namespace}:${id.key}`;
}

/**
 * Pluggable loader for one resource. Swap the implementation (fetch, IndexedDB,
 * etc.) without rewriting CachedResourceProxy consumers.
 */
export type DataSource<T> = {
  read(): Promise<T>;
};

/** Default freshness window for navigation read caching (10 minutes). */
export const DEFAULT_RESOURCE_CACHE_TTL_MS = 10 * 60 * 1000;

export type ResourceCacheOptions = {
  /**
   * Freshness window in ms. Expired entries are a miss (no stale-while-revalidate).
   * Default: {@link DEFAULT_RESOURCE_CACHE_TTL_MS} — long enough to skip repeat GETs
   * when navigating away and back within a session; mutations must set/invalidate.
   */
  ttlMs?: number;
  /** Injectable clock for tests. */
  now?: () => number;
};
