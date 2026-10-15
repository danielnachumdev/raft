import assert from "node:assert/strict";
import { describe, it, beforeEach } from "node:test";
import { loadTrendsViewsStore } from "../../../src/trends/views/storage.ts";
import {
  EMPTY_VIEWS_STORE,
  TRENDS_VIEWS_STORAGE_KEY,
} from "../../../src/trends/views/types.ts";
import { defaultRangeState } from "../../../src/trends/range/index.ts";
import { parseStore } from "../../../src/trends/views/parseStore.ts";
import { installMemoryStorage } from "../memoryStorage.ts";

let memory: Map<string, string>;

describe("legacy trends views (read-only)", () => {
  beforeEach(() => {
    memory = installMemoryStorage();
  });

  it("reads a #202 named view from localStorage", () => {
    memory.set(
      TRENDS_VIEWS_STORAGE_KEY,
      JSON.stringify({
        version: 1,
        activeId: "view-a",
        views: [
          {
            id: "view-a",
            name: " demo stack ",
            updatedAt: "2026-10-01T00:00:00.000Z",
            config: {
              metricIds: ["cpu_percent", "rps", "not-a-metric"],
              viewMode: "per_service",
              selected: ["demo-api"],
              range: defaultRangeState(),
            },
          },
        ],
      }),
    );
    const loaded = loadTrendsViewsStore();
    assert.equal(loaded.activeId, "view-a");
    assert.equal(loaded.views[0].name, "demo stack");
    assert.deepEqual(loaded.views[0].config.metricIds, ["cpu_percent", "rps"]);
  });

  it("returns an empty store when the key is missing", () => {
    assert.deepEqual(loadTrendsViewsStore(), EMPTY_VIEWS_STORE);
  });

  it("rejects corrupt localStorage payloads", () => {
    memory.set(TRENDS_VIEWS_STORAGE_KEY, "{not-json");
    assert.deepEqual(loadTrendsViewsStore(), EMPTY_VIEWS_STORE);
    assert.deepEqual(parseStore({ version: 2, views: [] }), EMPTY_VIEWS_STORE);
    assert.deepEqual(
      parseStore({
        version: 1,
        activeId: "x",
        views: [{ id: "x", name: "", updatedAt: "t", config: null }],
      }),
      { version: 1, activeId: null, views: [] },
    );
  });
});
