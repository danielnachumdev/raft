import type { ResourceCache } from "./ResourceCache.ts";
import type { DataSource, ResourceId } from "./types.ts";

/**
 * CRUD-shaped proxy: reads go through the cache; writes forward to the real
 * data source, then update or invalidate so the next read stays correct.
 *
 * - read: cache hit when fresh, else source.read + store
 * - write: source mutation returns the new value → replace cache entry
 * - mutateAndInvalidate: source mutation returns something else → drop entry
 */
export class CachedResourceProxy<T> {
  private readonly cache: ResourceCache;
  private readonly id: ResourceId;
  private readonly source: DataSource<T>;

  constructor(
    cache: ResourceCache,
    id: ResourceId,
    source: DataSource<T>,
  ) {
    this.cache = cache;
    this.id = id;
    this.source = source;
  }

  read(): Promise<T> {
    return this.cache.readThrough(this.id, this.source);
  }

  /** Bypass TTL: always load from source and replace the cache entry. */
  async refresh(): Promise<T> {
    const value = await this.source.read();
    this.cache.set(this.id, value);
    return value;
  }

  /** Create/Update when the source returns the authoritative resource value. */
  async write(mutate: () => Promise<T>): Promise<T> {
    const value = await mutate();
    this.cache.set(this.id, value);
    return value;
  }

  /** Delete / opaque mutation: run source op, then invalidate. */
  async mutateAndInvalidate<R>(mutate: () => Promise<R>): Promise<R> {
    const result = await mutate();
    this.cache.invalidate(this.id);
    return result;
  }

  invalidate(): void {
    this.cache.invalidate(this.id);
  }
}
