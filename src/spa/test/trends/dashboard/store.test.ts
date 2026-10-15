import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";
import {
  defaultDashboard,
  defaultDashboardStore,
  defaultPanels,
  loadDashboardStore,
  migrateLegacyViews,
  parseDashboardStore,
  parseGraph,
  saveDashboardStore,
  TRENDS_DASHBOARDS_STORAGE_KEY,
} from "../../../src/trends/dashboard/model/index.ts";
import { defaultRangeState } from "../../../src/trends/range/index.ts";
import {
  TRENDS_VIEWS_STORAGE_KEY,
  type TrendsViewsStore,
} from "../../../src/trends/views/types.ts";
import { installMemoryStorage } from "../memoryStorage.ts";

let memory: Map<string, string>;

const legacy = (): TrendsViewsStore => ({
  version: 1,
  activeId: "view-b",
  views: [
    view("view-a", "demo cpu", ["cpu_percent"], null),
    view("view-b", "demo http", ["rps", "duration_p95_ms"], ["demo-api"]),
  ],
});

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

describe("dashboard store load + migrate", () => {
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

  it("migrates #202 named views into one dashboard each", () => {
    memory.set(TRENDS_VIEWS_STORAGE_KEY, JSON.stringify(legacy()));
    const got = loadDashboardStore();
    assert.deepEqual(
      got.dashboards.map((d) => d.name),
      ["Overview", "demo cpu", "demo http"],
    );
    assert.equal(got.activeId, "view-b");
    const http = got.dashboards[2];
    assert.equal(http.range.windowSec, 21600);
    assert.equal(http.panels.length, 1);
    assert.equal(http.panels[0].size, "full");
    assert.deepEqual(http.panels[0].metricIds, ["rps", "duration_p95_ms"]);
    assert.deepEqual(http.panels[0].selected, ["demo-api"]);
  });

  it("keeps Overview active when no legacy view was active", () => {
    const got = migrateLegacyViews({ ...legacy(), activeId: null });
    assert.equal(got.activeId, "overview");
  });

  it("prefers the v2 store over legacy views once it exists", () => {
    memory.set(TRENDS_VIEWS_STORAGE_KEY, JSON.stringify(legacy()));
    saveDashboardStore(defaultDashboardStore());
    assert.equal(loadDashboardStore().dashboards.length, 1);
  });
});

function view(
  id: string,
  name: string,
  metricIds: string[],
  selected: string[] | null,
) {
  return {
    id,
    name,
    updatedAt: "2026-10-01T00:00:00.000Z",
    config: {
      metricIds,
      viewMode: "per_service",
      selected,
      range: { ...defaultRangeState(), windowSec: 21600 },
    },
  } as TrendsViewsStore["views"][number];
}
