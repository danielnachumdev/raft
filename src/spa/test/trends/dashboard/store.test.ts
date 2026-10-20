import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";
import {
  defaultDashboard,
  defaultDashboardStore,
  defaultPanels,
  loadDashboardStore,
  parseDashboardStore,
  parseGraph,
  saveDashboardStore,
  TRENDS_DASHBOARDS_STORAGE_KEY,
} from "../../../src/trends/dashboard/model/index.ts";
import { defaultRangeState } from "../../../src/trends/range/index.ts";
import { installMemoryStorage } from "../memoryStorage.ts";

let memory: Map<string, string>;

describe("default dashboard layout", () => {
  it("ships six half-width, all-service graphs in a stable order", () => {
    const panels = defaultPanels();
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
    assert.ok(panels.every((p) => p.size === "half" && p.selected === null));
    assert.ok(panels.every((p) => p.viewMode === "per_service"));
    assert.equal(new Set(panels.map((p) => p.id)).size, panels.length);
  });

  it("returns fresh copies (no shared mutable state)", () => {
    const a = defaultPanels();
    a[0].metricIds.push("pids");
    assert.deepEqual(defaultPanels()[0].metricIds, ["cpu_percent"]);
  });

  it("defaults the Overview range to the 1h preset", () => {
    assert.deepEqual(defaultDashboard().range, defaultRangeState());
  });
});

describe("dashboard store parse", () => {
  it("round-trips through localStorage", () => {
    memory = installMemoryStorage();
    const store = defaultDashboardStore(1_700_000_000_000);
    saveDashboardStore(store);
    assert.deepEqual(loadDashboardStore(), store);
  });

  it("rejects corrupt or foreign payloads", () => {
    assert.equal(parseDashboardStore(null), null);
    assert.equal(parseDashboardStore("nope"), null);
    assert.equal(parseDashboardStore({ version: 1, dashboards: [] }), null);
    assert.equal(parseDashboardStore({ version: 2, dashboards: [] }), null);
    assert.equal(
      parseDashboardStore({ version: 2, dashboards: [{ id: "x", name: "" }] }),
      null,
    );
  });

  it("drops invalid graphs, duplicate ids, and falls back activeId", () => {
    const d = defaultDashboard(1);
    const raw = {
      version: 2,
      activeId: "missing",
      dashboards: [
        { ...d, panels: [d.panels[0], d.panels[0], { id: "bad", size: "huge" }] },
        { ...d },
      ],
    };
    const got = parseDashboardStore(raw)!;
    assert.equal(got.activeId, d.id);
    assert.equal(got.dashboards.length, 1);
    assert.deepEqual(got.dashboards[0].panels.map((p) => p.id), [d.panels[0].id]);
  });

  it("filters unknown metrics and caps graphs at two metric types", () => {
    const g = parseGraph({
      id: "g",
      title: " t ",
      metricIds: ["cpu_percent", "bogus", "rps", "network_rx_bytes"],
      viewMode: "per_service",
      selected: null,
      size: "full",
    })!;
    assert.equal(g.title, "t");
    assert.deepEqual(g.metricIds, ["cpu_percent", "rps"]);
  });
});

describe("dashboard store load", () => {
  beforeEach(() => {
    memory = installMemoryStorage();
  });

  it("starts with the Overview dashboard when nothing is stored", () => {
    const got = loadDashboardStore();
    assert.equal(got.dashboards.length, 1);
    assert.equal(got.dashboards[0].name, "Overview");
    assert.equal(got.activeId, got.dashboards[0].id);
  });

  it("falls back to defaults on corrupt JSON", () => {
    memory.set(TRENDS_DASHBOARDS_STORAGE_KEY, "{not-json");
    assert.equal(loadDashboardStore().dashboards[0].name, "Overview");
  });
});
