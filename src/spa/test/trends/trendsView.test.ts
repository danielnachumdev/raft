import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  buildPerGroupSeries,
  isSingleLineAvg,
  resolveVisibleSeries,
  seriesInGroups,
  UNGROUPED_ID,
} from "../../src/trends/panel/trendsView.ts";
import { metricsSeries } from "../fixtures.ts";

const sample = [
  metricsSeries("host", null, [{ t: "t1", cpu: 90 }]),
  metricsSeries("demo-web", "demo", [
    { t: "t1", cpu: 10, mem: 40 },
    { t: "t2", cpu: 20, mem: 50 },
  ]),
  metricsSeries("demo-api", "demo", [
    { t: "t1", cpu: 30, mem: 60 },
    { t: "t2", cpu: 40, mem: 70 },
  ]),
  metricsSeries("solo", null, [{ t: "t1", cpu: 50 }]),
];

describe("isSingleLineAvg", () => {
  it("is true only for avg_all", () => {
    assert.equal(isSingleLineAvg("avg_all"), true);
    assert.equal(isSingleLineAvg("avg_group"), false);
    assert.equal(isSingleLineAvg("per_group"), false);
    assert.equal(isSingleLineAvg("per_service"), false);
  });
});

describe("buildPerGroupSeries", () => {
  it("emits one mean series per selected group with all metric fields", () => {
    const got = buildPerGroupSeries(sample, ["demo", UNGROUPED_ID]);
    assert.deepEqual(
      got.map((s) => s.id),
      ["group:demo", `group:${UNGROUPED_ID}`],
    );
    const demo = got[0];
    assert.equal(demo.label, "demo");
    assert.equal(demo.kind, "group");
    assert.equal(demo.points[0].cpu_percent, 20);
    assert.equal(demo.points[0].memory_used_percent, 50);
    assert.equal(demo.points[1].cpu_percent, 30);
    assert.equal(demo.points[1].memory_used_percent, 60);
    assert.equal(got[1].points[0].cpu_percent, 50);
  });
});

describe("resolveVisibleSeries", () => {
  it("avg_group plots one averaged line per group (not a global avg)", () => {
    const got = resolveVisibleSeries({
      series: sample,
      viewMode: "avg_group",
      selected: null,
      activeIds: ["demo", UNGROUPED_ID],
    });
    assert.equal(got.length, 2);
    assert.deepEqual(
      got.map((s) => s.id),
      ["group:demo", `group:${UNGROUPED_ID}`],
    );
    assert.equal(got[0].points[0].cpu_percent, 20);
  });

  it("avg_group respects the group sidebar selection", () => {
    const got = resolveVisibleSeries({
      series: sample,
      viewMode: "avg_group",
      selected: ["demo"],
      activeIds: ["demo"],
    });
    assert.equal(got.length, 1);
    assert.equal(got[0].id, "group:demo");
  });

  it("per_service filters by selected service ids", () => {
    const got = resolveVisibleSeries({
      series: sample,
      viewMode: "per_service",
      selected: ["demo-web"],
      activeIds: ["demo-web"],
    });
    assert.deepEqual(
      got.map((s) => s.id),
      ["demo-web"],
    );
  });
});

describe("seriesInGroups", () => {
  it("returns member services only", () => {
    const got = seriesInGroups(sample, ["demo"]);
    assert.deepEqual(
      got.map((s) => s.id),
      ["demo-web", "demo-api"],
    );
  });
});
