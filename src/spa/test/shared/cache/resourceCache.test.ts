import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  CachedResourceProxy,
  ResourceCache,
  resourceId,
  resourceIdString,
} from "../../../src/shared/cache/index.ts";

describe("resourceId", () => {
  it("formats namespace:key", () => {
    assert.equal(resourceIdString(resourceId("fw", "doc")), "fw:doc");
  });
});

describe("ResourceCache", () => {
  it("misses then stores a read-through", async () => {
    let reads = 0;
    const cache = new ResourceCache({ ttlMs: 60_000 });
    const id = resourceId("demo", "item");
    const source = {
      read: async () => {
        reads += 1;
        return { n: reads };
      },
    };

    assert.equal(cache.peek(id), null);
    const first = await cache.readThrough(id, source);
    assert.deepEqual(first, { n: 1 });
    assert.equal(reads, 1);

    const second = await cache.readThrough(id, source);
    assert.deepEqual(second, { n: 1 });
    assert.equal(reads, 1);
  });

  it("expires entries after ttl", async () => {
    let now = 1_000;
    const cache = new ResourceCache({ ttlMs: 100, now: () => now });
    const id = resourceId("demo", "ttl");
    let reads = 0;
    const source = {
      read: async () => {
        reads += 1;
        return reads;
      },
    };

    assert.equal(await cache.readThrough(id, source), 1);
    now = 1_050;
    assert.equal(await cache.readThrough(id, source), 1);
    now = 1_101;
    assert.equal(cache.peek(id), null);
    assert.equal(await cache.readThrough(id, source), 2);
  });

  it("invalidates one key or a whole namespace", () => {
    const cache = new ResourceCache();
    cache.set(resourceId("a", "1"), "x");
    cache.set(resourceId("a", "2"), "y");
    cache.set(resourceId("b", "1"), "z");

    cache.invalidate(resourceId("a", "1"));
    assert.equal(cache.peek(resourceId("a", "1")), null);
    assert.equal(cache.peek(resourceId("a", "2")), "y");

    cache.invalidateNamespace("a");
    assert.equal(cache.peek(resourceId("a", "2")), null);
    assert.equal(cache.peek(resourceId("b", "1")), "z");
  });
});

describe("CachedResourceProxy CRUD", () => {
  it("read hits cache; write replaces; mutateAndInvalidate drops", async () => {
    const cache = new ResourceCache({ ttlMs: 60_000 });
    const id = resourceId("channels", "list");
    let remote = ["a"];
    let reads = 0;

    const proxy = new CachedResourceProxy(cache, id, {
      read: async () => {
        reads += 1;
        return [...remote];
      },
    });

    assert.deepEqual(await proxy.read(), ["a"]);
    assert.deepEqual(await proxy.read(), ["a"]);
    assert.equal(reads, 1);

    await proxy.write(async () => {
      remote = ["a", "b"];
      return [...remote];
    });
    assert.deepEqual(await proxy.read(), ["a", "b"]);
    assert.equal(reads, 1);

    await proxy.mutateAndInvalidate(async () => {
      remote = ["a"];
      return { ok: true as const, deleted: "b" };
    });
    assert.equal(cache.peek(id), null);
    assert.deepEqual(await proxy.read(), ["a"]);
    assert.equal(reads, 2);
  });

  it("refresh bypasses ttl and replaces the entry", async () => {
    const cache = new ResourceCache({ ttlMs: 60_000 });
    const id = resourceId("demo", "refresh");
    let value = 1;
    const proxy = new CachedResourceProxy(cache, id, {
      read: async () => value,
    });

    assert.equal(await proxy.read(), 1);
    value = 2;
    assert.equal(await proxy.refresh(), 2);
    assert.equal(await proxy.read(), 2);
  });
});
