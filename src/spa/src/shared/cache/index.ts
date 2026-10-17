import { ResourceCache } from "./ResourceCache.ts";
import { CachedResourceProxy } from "./CachedResourceProxy.ts";
import {
  DEFAULT_RESOURCE_CACHE_TTL_MS,
  resourceId,
  resourceIdString,
} from "./types.ts";

export type {
  DataSource,
  ResourceCacheOptions,
  ResourceId,
} from "./types.ts";
export {
  DEFAULT_RESOURCE_CACHE_TTL_MS,
  resourceId,
  resourceIdString,
  ResourceCache,
  CachedResourceProxy,
};

/**
 * Shared process cache for serve SPA resource GETs (firewall, notifications, …).
 * Inject a fresh ResourceCache in unit tests instead of this singleton.
 */
export const appResourceCache = new ResourceCache({
  ttlMs: DEFAULT_RESOURCE_CACHE_TTL_MS,
});
