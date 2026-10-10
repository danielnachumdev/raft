import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  formatMetricValue,
  METRIC_TYPES,
  metricType,
  uniqueTypeIds,
  yAxisSuffix,
} from "../../src/trends/metricTypes.ts";
import { RUNTIME_METRICS } from "../../src/trends/runtimeMetrics.ts";

describe("METRIC_TYPES registry", () => {
  it("exposes the shipped type ids", () => {
    assert.deepEqual(
      METRIC_TYPES.map((t) => t.id),
      ["percent", "count", "duration", "bytes", "rate", "uptime"],
    );
  });

  it("looks up type defs by id", () => {
    assert.equal(metricType("percent").label, "Percent");
    assert.equal(yAxisSuffix("duration"), "ms");
    assert.equal(formatMetricValue(12.34, "duration"), "12.3 ms");
    assert.equal(formatMetricValue(2.5, "rate"), "2.50/s");
  });

  it("orders uniqueTypeIds by registry, not selection order", () => {
    assert.deepEqual(uniqueTypeIds(["rate", "percent", "count"]), [
      "percent",
      "count",
      "rate",
    ]);
  });
});

describe("metric → type mapping", () => {
  it("assigns every catalog metric a registered type", () => {
    const known = new Set(METRIC_TYPES.map((t) => t.id));
    for (const m of RUNTIME_METRICS) {
      assert.ok(known.has(m.typeId), `${m.id} has unknown type ${m.typeId}`);
    }
  });

  it("maps status codes and pids to count", () => {
    for (const id of [
      "pids",
      "in_flight",
      "status_2xx",
      "status_3xx",
      "status_4xx",
      "status_5xx",
    ]) {
      assert.equal(
        RUNTIME_METRICS.find((m) => m.id === id)?.typeId,
        "count",
        id,
      );
    }
  });

  it("maps latencies to duration and uptime to uptime", () => {
    for (const id of [
      "duration_avg_ms",
      "duration_p50_ms",
      "duration_p95_ms",
      "duration_p99_ms",
    ]) {
      assert.equal(
        RUNTIME_METRICS.find((m) => m.id === id)?.typeId,
        "duration",
        id,
      );
    }
    assert.equal(
      RUNTIME_METRICS.find((m) => m.id === "uptime_seconds")?.typeId,
      "uptime",
    );
  });
});
