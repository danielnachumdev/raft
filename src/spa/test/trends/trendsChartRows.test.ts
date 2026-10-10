import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { MetricsSeries } from "../../src/shared/api.ts";
import { RUNTIME_METRICS } from "../../src/trends/runtimeMetrics.ts";
import {
  aggregatePlots,
  axisForType,
  buildAggregateRows,
  buildPerServiceRows,
  LEFT_AXIS,
  needsSplitAxes,
  RIGHT_AXIS,
  toPlotSeries,
  typeIdsForMetrics,
} from "../../src/trends/chart/trendsChartRows.ts";

function series(
  id: string,
  cpu: number,
  mem: number,
  kind: MetricsSeries["kind"] = "container",
): MetricsSeries {
  return {
    id,
    label: id,
    kind,
    role: "app",
    group: null,
    points: [
      {
        t: "2024-01-01T00:00:00Z",
        cpu_percent: cpu,
        memory_used_percent: mem,
        memory_used_bytes: null,
        status_2xx: 10,
        status_5xx: 1,
        duration_p95_ms: 40,
      },
    ],
  };
}

const cpu = RUNTIME_METRICS.find((m) => m.id === "cpu_percent")!;
const mem = RUNTIME_METRICS.find((m) => m.id === "memory_used_percent")!;
const s2xx = RUNTIME_METRICS.find((m) => m.id === "status_2xx")!;
const s5xx = RUNTIME_METRICS.find((m) => m.id === "status_5xx")!;
const p95 = RUNTIME_METRICS.find((m) => m.id === "duration_p95_ms")!;

describe("toPlotSeries", () => {
  it("emits one plot per service when a single metric is selected", () => {
    const plots = toPlotSeries([series("a", 1, 2), series("b", 3, 4)], [cpu]);
    assert.equal(plots.length, 2);
    assert.equal(plots[0].label, "a");
    assert.equal(plots[0].metricId, "cpu_percent");
    assert.equal(plots[0].typeId, "percent");
  });

  it("labels service · metric when multiple metrics are selected", () => {
    const plots = toPlotSeries([series("a", 1, 2)], [cpu, mem]);
    assert.equal(plots.length, 2);
    assert.equal(plots[0].label, "a · CPU %");
    assert.equal(plots[1].label, "a · Memory used %");
    assert.equal(plots[0].axis, LEFT_AXIS);
    assert.equal(plots[1].axis, LEFT_AXIS);
  });

  it("shares one axis for same-type multi-select (counts)", () => {
    const plots = toPlotSeries([series("demo-api", 1, 2)], [s2xx, s5xx]);
    assert.equal(plots.every((p) => p.axis === LEFT_AXIS), true);
    assert.equal(needsSplitAxes([series("demo-api", 1, 2)], [s2xx, s5xx]), false);
  });

  it("assigns dual axes by type registry order, not selection order", () => {
    // count before percent in selection, but percent is first in registry
    const plots = toPlotSeries([series("demo-web", 1, 2)], [s2xx, cpu]);
    const types = typeIdsForMetrics([s2xx, cpu]);
    assert.deepEqual(types, ["percent", "count"]);
    assert.equal(plots.find((p) => p.metricId === "cpu_percent")?.axis, LEFT_AXIS);
    assert.equal(plots.find((p) => p.metricId === "status_2xx")?.axis, RIGHT_AXIS);
  });

  it("maps two types to left and right axes", () => {
    const types = typeIdsForMetrics([cpu, s2xx]);
    assert.deepEqual(types, ["percent", "count"]);
    assert.equal(axisForType("percent", types), LEFT_AXIS);
    assert.equal(axisForType("count", types), RIGHT_AXIS);
  });
});

describe("multi-metric rows", () => {
  it("builds per-service rows with a column per metric", () => {
    const sample = [series("web", 10, 40)];
    const plots = toPlotSeries(sample, [cpu, mem]);
    const rows = buildPerServiceRows(sample, plots);
    assert.equal(rows.length, 1);
    assert.equal(rows[0][plots[0].chartKey], 10);
    assert.equal(rows[0][plots[1].chartKey], 40);
  });

  it("builds one aggregate line per metric", () => {
    const sample = [series("a", 10, 40), series("b", 30, 60)];
    const plots = aggregatePlots([cpu, mem]);
    const rows = buildAggregateRows(sample, plots);
    assert.equal(rows.length, 1);
    assert.equal(rows[0][plots[0].chartKey], 20);
    assert.equal(rows[0][plots[1].chartKey], 50);
  });

  it("keeps duration metrics on one shared axis", () => {
    const avg = RUNTIME_METRICS.find((m) => m.id === "duration_avg_ms")!;
    const plots = toPlotSeries([series("demo-api", 1, 2)], [avg, p95]);
    assert.equal(plots.every((p) => p.typeId === "duration"), true);
    assert.equal(plots.every((p) => p.axis === LEFT_AXIS), true);
  });
});

describe("host with single type", () => {
  it("keeps host on the shared left axis (same type as services)", () => {
    const host = series("host", 5, 5, "host");
    const app = series("demo-api", 1, 2);
    assert.equal(needsSplitAxes([host, app], [cpu]), false);
    const plots = toPlotSeries([host, app], [cpu]);
    assert.equal(plots.every((p) => p.axis === LEFT_AXIS), true);
  });
});
