import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { defaultRangeState } from "../../../src/trends/range/index.ts";
import {
  blankServiceDraft,
  defaultServiceLayout,
  defaultServicePanels,
  emptyServiceTrendsStore,
  layoutForService,
  loadServiceTrendsStore,
  parseServiceTrendsStore,
  pinDraftToService,
  pinLayoutToService,
  putServiceLayout,
  saveServiceTrendsStore,
  SERVICE_TRENDS_STORAGE_KEY,
} from "../../../src/trends/service/model/index.ts";
import { installMemoryStorage } from "../memoryStorage.ts";

describe("default service Trends layout", () => {
  it("ships six half-width graphs pinned to the service", () => {
    const panels = defaultServicePanels("demo-api");
    assert.deepEqual(
      panels.map((p) => p.metricIds),
      [
        ["cpu_percent"],
        ["memory_used_percent"],
        ["rps"],
        ["duration_p95_ms"],
        ["status_4xx", "status_5xx"],
        ["network_rx_bytes", "network_tx_bytes"],
      ],
    );
    assert.ok(panels.every((p) => p.size === "half"));
    assert.ok(panels.every((p) => p.viewMode === "per_service"));
    assert.ok(panels.every((p) => p.selected?.length === 1 && p.selected[0] === "demo-api"));
    assert.equal(new Set(panels.map((p) => p.id)).size, panels.length);
  });

  it("returns fresh copies (no shared mutable state)", () => {
    const a = defaultServicePanels("demo-api");
    a[0].metricIds.push("pids");
    a[0].selected!.push("other");
    assert.deepEqual(defaultServicePanels("demo-api")[0].metricIds, ["cpu_percent"]);
    assert.deepEqual(defaultServicePanels("demo-api")[0].selected, ["demo-api"]);
  });

  it("defaults the range to the 1h preset", () => {
    assert.deepEqual(defaultServiceLayout("demo-api").range, defaultRangeState());
  });

  it("blank add draft is already pinned", () => {
    const draft = blankServiceDraft("demo-web");
    assert.deepEqual(draft.selected, ["demo-web"]);
    assert.equal(draft.viewMode, "per_service");
  });
});

describe("service Trends store parse / persist", () => {
  it("round-trips through localStorage", () => {
    installMemoryStorage();
    const layout = defaultServiceLayout("demo-api", 1_700_000_000_000);
    const store = putServiceLayout(emptyServiceTrendsStore(), "demo-api", layout);
    saveServiceTrendsStore(store);
    assert.deepEqual(loadServiceTrendsStore(), store);
    assert.ok(localStorage.getItem(SERVICE_TRENDS_STORAGE_KEY));
  });

  it("rejects corrupt or foreign payloads", () => {
    assert.equal(parseServiceTrendsStore(null), null);
    assert.equal(parseServiceTrendsStore("nope"), null);
    assert.equal(parseServiceTrendsStore({ version: 2, services: {} }), null);
    assert.equal(parseServiceTrendsStore({ version: 1 }), null);
  });

  it("drops invalid layouts and keeps valid ones", () => {
    const good = defaultServiceLayout("demo-api", 1);
    const got = parseServiceTrendsStore({
      version: 1,
      services: {
        "demo-api": good,
        "": good,
        bad: { updatedAt: "x" },
        "demo-web": {
          ...good,
          panels: [good.panels[0], good.panels[0], { id: "bad", size: "huge" }],
        },
      },
    })!;
    assert.deepEqual(Object.keys(got.services).sort(), ["demo-api", "demo-web"]);
    assert.deepEqual(
      got.services["demo-web"].panels.map((p) => p.id),
      [good.panels[0].id],
    );
  });

  it("layoutForService returns defaults when unsaved", () => {
    const store = emptyServiceTrendsStore();
    const layout = layoutForService(store, "demo-api", 1_700_000_000_000);
    assert.equal(layout.panels.length, 6);
    assert.deepEqual(layout.panels[0].selected, ["demo-api"]);
  });

  it("layoutForService returns a copy of a saved layout", () => {
    const saved = defaultServiceLayout("demo-api", 1);
    saved.panels[0].title = "Custom CPU";
    const store = putServiceLayout(emptyServiceTrendsStore(), "demo-api", saved);
    const got = layoutForService(store, "demo-api");
    got.panels[0].title = "mutated";
    assert.equal(store.services["demo-api"].panels[0].title, "Custom CPU");
  });

  it("falls back to empty store on corrupt localStorage", () => {
    const memory = installMemoryStorage();
    memory.set(SERVICE_TRENDS_STORAGE_KEY, "{not-json");
    assert.deepEqual(loadServiceTrendsStore(), emptyServiceTrendsStore());
  });
});

describe("pin to service", () => {
  it("forces per_service and a single selected id", () => {
    const pinned = pinDraftToService(
      {
        title: "CPU",
        metricIds: ["cpu_percent"],
        viewMode: "avg_all",
        selected: null,
        size: "full",
      },
      "demo-api",
    );
    assert.equal(pinned.viewMode, "per_service");
    assert.deepEqual(pinned.selected, ["demo-api"]);
  });

  it("re-pins every panel on a layout", () => {
    const layout = defaultServiceLayout("old-name", 1);
    layout.panels[0].selected = ["other"];
    layout.panels[0].viewMode = "avg_group";
    const pinned = pinLayoutToService(layout, "demo-api");
    assert.ok(
      pinned.panels.every(
        (p) => p.viewMode === "per_service" && p.selected?.[0] === "demo-api",
      ),
    );
  });
});
