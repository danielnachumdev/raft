import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { MetricsSeries } from "../../src/shared/api.ts";
import { RUNTIME_METRICS } from "../../src/trends/runtimeMetrics.ts";
import {
  aggregatePlots,
  buildAggregateRows,
  buildPerServiceRows,
  toPlotSeries,
} from "../../src/trends/panel/trendsChartRows.ts";

function series(id: string, cpu: number, mem: number): MetricsSeries {
  return {
    id,
    label: id,
    kind: "container",
    role: "app",
    group: null,
    points: [
      {
        t: "2024-01-01T00:00:00Z",
        cpu_percent: cpu,
        memory_used_percent: mem,
        memory_used_bytes: null,
      },
    ],
  };
}

const cpu = RUNTIME_METRICS.find((m) => m.id === "cpu_percent")!;
const mem = RUNTIME_METRICS.find((m) => m.id === "memory_used_percent")!;

describe("toPlotSeries", () => {
  it("emits one plot per service when a single metric is selected", () => {
    const plots = toPlotSeries([series("a", 1, 2), series("b", 3, 4)], [cpu]);
    assert.equal(plots.length, 2);
    assert.equal(plots[0].label, "a");
    assert.equal(plots[0].metricId, "cpu_percent");
  });

  it("labels service · metric when multiple metrics are selected", () => {
    const plots = toPlotSeries([series("a", 1, 2)], [cpu, mem]);
    assert.equal(plots.length, 2);
    assert.equal(plots[0].label, "a · CPU %");
    assert.equal(plots[1].label, "a · Memory used %");
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
});
