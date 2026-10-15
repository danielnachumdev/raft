import assert from "node:assert/strict";
import { describe, it, beforeEach } from "node:test";
import {
  createNamedView,
  deleteView,
  loadTrendsViewsStore,
  renameView,
  saveTrendsViewsStore,
  setActiveViewId,
  updateActiveConfig,
  upsertView,
} from "../../../src/trends/views/storage.ts";
import {
  EMPTY_VIEWS_STORE,
  TRENDS_VIEWS_STORAGE_KEY,
  type TrendsViewConfig,
} from "../../../src/trends/views/types.ts";
import { defaultRangeState } from "../../../src/trends/range/index.ts";
import { parseStore } from "../../../src/trends/views/parseStore.ts";

const memory = new Map<string, string>();

const sampleConfig = (): TrendsViewConfig => ({
  metricIds: ["cpu_percent", "rps"],
  viewMode: "per_service",
  selected: ["demo-api"],
  range: defaultRangeState(),
});

describe("trends views storage", () => {
  beforeEach(() => {
    memory.clear();
    globalThis.localStorage = {
      getItem: (k: string) => memory.get(k) ?? null,
      setItem: (k: string, v: string) => {
        memory.set(k, v);
      },
      removeItem: (k: string) => {
        memory.delete(k);
      },
      clear: () => memory.clear(),
      key: () => null,
      length: 0,
    };
  });

  it("round-trips a saved view through localStorage", () => {
    const view = createNamedView("demo stack", sampleConfig(), 1_700_000_000_000);
    const store = upsertView({ ...EMPTY_VIEWS_STORE }, view);
    saveTrendsViewsStore(store);
    const loaded = loadTrendsViewsStore();
    assert.equal(loaded.activeId, view.id);
    assert.equal(loaded.views.length, 1);
    assert.equal(loaded.views[0].name, "demo stack");
    assert.deepEqual(loaded.views[0].config.metricIds, ["cpu_percent", "rps"]);
    assert.deepEqual(loaded.views[0].config.selected, ["demo-api"]);
  });

  it("renames, updates config, and deletes views", () => {
    const view = createNamedView("v1", sampleConfig(), 1);
    let store = upsertView({ ...EMPTY_VIEWS_STORE }, view);
    store = renameView(store, view.id, "v1-renamed");
    assert.equal(store.views[0].name, "v1-renamed");
    const next = { ...sampleConfig(), selected: null };
    store = updateActiveConfig(store, next, 2);
    assert.equal(store.views[0].config.selected, null);
    store = deleteView(store, view.id);
    assert.deepEqual(store.views, []);
    assert.equal(store.activeId, null);
  });

  it("clears activeId when selecting a missing view", () => {
    const store = setActiveViewId(
      { version: 1, activeId: "x", views: [] },
      "missing",
    );
    assert.equal(store.activeId, null);
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
