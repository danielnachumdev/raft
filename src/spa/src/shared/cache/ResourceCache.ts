import {
  DEFAULT_RESOURCE_CACHE_TTL_MS,
  resourceIdString,
  type ResourceCacheOptions,
  type ResourceId,
  type DataSource,
} from "./types.ts";

type Entry = {
  value: unknown;
  fetchedAt: number;
};

/**
 * In-memory TTL store keyed by resource identity.
 *
 * Policy: hit when age < ttlMs; otherwise miss and drop the entry.
 * No background revalidate — keep this a thin proxy, not a store framework.
 * Mutative callers use CachedResourceProxy to set or invalidate after source I/O.
 */
export class ResourceCache {
  private readonly entries = new Map<string, Entry>();
  private readonly ttlMs: number;
  private readonly now: () => number;

  constructor(options: ResourceCacheOptions = {}) {
    this.ttlMs = options.ttlMs ?? DEFAULT_RESOURCE_CACHE_TTL_MS;
    this.now = options.now ?? Date.now;
  }

  peek<T>(id: ResourceId): T | null {
    const key = resourceIdString(id);
    const entry = this.entries.get(key);
    if (!entry) return null;
    if (this.now() - entry.fetchedAt > this.ttlMs) {
      this.entries.delete(key);
      return null;
    }
    return entry.value as T;
  }

  set<T>(id: ResourceId, value: T): void {
    this.entries.set(resourceIdString(id), {
      value,
      fetchedAt: this.now(),
    });
  }

  invalidate(id: ResourceId): void {
    this.entries.delete(resourceIdString(id));
  }

  invalidateNamespace(namespace: string): void {
    const prefix = `${namespace}:`;
    for (const key of [...this.entries.keys()]) {
      if (key.startsWith(prefix)) this.entries.delete(key);
    }
  }

  clear(): void {
    this.entries.clear();
  }

  /** Read-through: return fresh hit, else load from source, store, return. */
  async readThrough<T>(id: ResourceId, source: DataSource<T>): Promise<T> {
    const hit = this.peek<T>(id);
    if (hit !== null) return hit;
    const value = await source.read();
    this.set(id, value);
    return value;
  }
}
