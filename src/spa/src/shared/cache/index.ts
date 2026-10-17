import { ResourceCache } from "./ResourceCache.ts";
import { CachedResourceProxy } from "./CachedResourceProxy.ts";
import { resourceId, resourceIdString } from "./types.ts";

export type {
  DataSource,
  ResourceCacheOptions,
  ResourceId,
} from "./types.ts";
export { resourceId, resourceIdString, ResourceCache, CachedResourceProxy };

/**
 * Shared process cache for serve SPA resource GETs (firewall, notifications, …).
 * Inject a fresh ResourceCache in unit tests instead of this singleton.
 */
export const appResourceCache = new ResourceCache({ ttlMs: 60_000 });
