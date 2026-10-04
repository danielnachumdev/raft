import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { MetricsSeries } from "../src/shared/api.ts";
import {
  buildPerGroupSeries,
  isSingleLineAvg,
  resolveVisibleSeries,
  seriesInGroups,
  UNGROUPED_ID,
} from "../src/trends/trendsView.ts";

function point(t: string, cpu: number | null) {
  return {
    t,
    cpu_percent: cpu,
    memory_used_percent: null,
    memory_used_bytes: null,
  };
}

function series(
  id: string,
  group: string | null,
  points: { t: string; cpu: number | null }[],
): MetricsSeries {
  return {
    id,
    label: id,
    kind: "container",
    role: "app",
    group,
    points: points.map((p) => point(p.t, p.cpu)),
  };
}

const sample: MetricsSeries[] = [
  series("host", null, [{ t: "t1", cpu: 90 }]),
  series("demo-web", "demo", [
    { t: "t1", cpu: 10 },
    { t: "t2", cpu: 20 },
  ]),
  series("demo-api", "demo", [
    { t: "t1", cpu: 30 },
    { t: "t2", cpu: 40 },
  ]),
  series("solo", null, [{ t: "t1", cpu: 50 }]),
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
  it("emits one mean series per selected group", () => {
    const got = buildPerGroupSeries(
      sample,
      ["demo", UNGROUPED_ID],
      "cpu_percent",
    );
    assert.deepEqual(
      got.map((s) => s.id),
      ["group:demo", `group:${UNGROUPED_ID}`],
    );
    const demo = got[0];
    assert.equal(demo.label, "demo");
    assert.equal(demo.kind, "group");
    assert.equal(demo.points[0].cpu_percent, 20);
    assert.equal(demo.points[1].cpu_percent, 30);
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
      metricId: "cpu_percent",
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
      metricId: "cpu_percent",
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
      metricId: "cpu_percent",
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
