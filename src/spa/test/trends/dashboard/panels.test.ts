import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  activeDashboard,
  addPanel,
  createDashboard,
  defaultDashboard,
  defaultDashboardStore,
  deleteDashboard,
  duplicatePanel,
  insertPanel,
  movePanel,
  movePanelTo,
  removePanel,
  renameDashboard,
  resizePanel,
  restoreDefaultPanels,
  setActiveDashboard,
  setDashboardRange,
  suggestDashboardName,
  updateActive,
  updatePanel,
  type TrendsDashboard,
  type TrendsGraphDraft,
} from "../../../src/trends/dashboard/model/index.ts";

const draft = (over: Partial<TrendsGraphDraft> = {}): TrendsGraphDraft => ({
  title: "Demo",
  metricIds: ["pids"],
  viewMode: "avg_all",
  selected: ["demo-api"],
  size: "full",
  ...over,
});

const ids = (d: TrendsDashboard) => d.panels.map((p) => p.id);
const base = () => defaultDashboard(0);

describe("graph reducers", () => {
  it("adds a graph at the end and clones the draft", () => {
    const src = draft();
    const d = addPanel(base(), src, "g-new");
    assert.equal(ids(d).at(-1), "g-new");
    src.metricIds.push("rps");
    assert.deepEqual(d.panels.at(-1)!.metricIds, ["pids"]);
    assert.notEqual(d.updatedAt, base().updatedAt);
  });

  it("edits a graph in place, keeping its id and slot", () => {
    const d = updatePanel(base(), "requests", draft({ title: "Edited" }));
    assert.equal(d.panels[2].id, "requests");
    assert.equal(d.panels[2].title, "Edited");
    assert.equal(d.panels.length, base().panels.length);
  });

  it("removes and re-inserts at the original index (undo)", () => {
    const original = base();
    const removed = removePanel(original, "latency");
    assert.ok(!ids(removed).includes("latency"));
    const back = insertPanel(removed, original.panels[3], 3);
    assert.deepEqual(ids(back), ids(original));
    assert.equal(insertPanel(back, original.panels[3], 0), back);
  });

  it("duplicates right after the source with a copy title", () => {
    const d = duplicatePanel(base(), "cpu", "cpu-2");
    assert.deepEqual(ids(d).slice(0, 2), ["cpu", "cpu-2"]);
    assert.equal(d.panels[1].title, "CPU (copy)");
    assert.equal(duplicatePanel(base(), "missing", "x").panels.length, 6);
  });

  it("moves by delta with clamping at the edges", () => {
    assert.deepEqual(ids(movePanel(base(), "memory", -1)).slice(0, 2), ["memory", "cpu"]);
    assert.deepEqual(ids(movePanel(base(), "cpu", -1)), ids(base()));
    assert.equal(ids(movePanel(base(), "cpu", 99)).at(-1), "cpu");
  });

  it("drag-drops into the target slot", () => {
    const d = movePanelTo(base(), "network", "cpu");
    assert.deepEqual(ids(d).slice(0, 2), ["network", "cpu"]);
    const down = movePanelTo(base(), "cpu", "latency");
    assert.equal(ids(down)[3], "cpu");
    assert.deepEqual(ids(movePanelTo(base(), "cpu", "nope")), ids(base()));
  });

  it("resizes and restores defaults", () => {
    const wide = resizePanel(base(), "cpu", "full");
    assert.equal(wide.panels[0].size, "full");
    const restored = restoreDefaultPanels(removePanel(wide, "cpu"));
    assert.deepEqual(ids(restored), ids(base()));
    assert.equal(restored.panels[0].size, "half");
  });

  it("stores a copy of the shared range", () => {
    const range = { ...base().range, windowSec: 900 };
    const d = setDashboardRange(base(), range);
    range.windowSec = 60;
    assert.equal(d.range.windowSec, 900);
  });
});

describe("dashboard store reducers", () => {
  it("creates, opens, renames, and deletes dashboards", () => {
    let s = createDashboard(defaultDashboardStore(0), "  Demo HTTP ", "dash-1");
    assert.equal(s.activeId, "dash-1");
    assert.equal(activeDashboard(s).name, "Demo HTTP");
    assert.deepEqual(activeDashboard(s).panels, []);
    s = renameDashboard(s, "dash-1", "Edge");
    assert.equal(activeDashboard(s).name, "Edge");
    assert.equal(renameDashboard(s, "dash-1", "  "), s);
    s = deleteDashboard(s, "dash-1");
    assert.equal(s.activeId, "overview");
    assert.equal(s.dashboards.length, 1);
  });

  it("replaces the last dashboard with a fresh Overview", () => {
    const s = deleteDashboard(defaultDashboardStore(0), "overview");
    assert.equal(s.dashboards.length, 1);
    assert.equal(s.dashboards[0].panels.length, 6);
  });

  it("only edits the active dashboard", () => {
    let s = createDashboard(defaultDashboardStore(0), "Second", "dash-2");
    s = updateActive(s, (d) => addPanel(d, draft(), "g"));
    s = setActiveDashboard(s, "overview");
    assert.equal(activeDashboard(s).panels.length, 6);
    assert.equal(setActiveDashboard(s, "missing"), s);
  });

  it("suggests an unused dashboard name", () => {
    const s = createDashboard(defaultDashboardStore(0), "Dashboard 2", "d2");
    assert.equal(suggestDashboardName(s), "Dashboard 3");
    assert.equal(createDashboard(s, "dup", "d2"), s);
  });
});
