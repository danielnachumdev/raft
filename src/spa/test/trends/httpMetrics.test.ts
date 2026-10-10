import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  HTTP_METRICS,
  RESOURCE_METRICS,
  RUNTIME_METRICS,
  formatRuntimeValue,
  runtimePointValue,
  type RuntimeMetricId,
} from "../../src/trends/runtimeMetrics.ts";

describe("HTTP trend metrics catalog", () => {
  it("keeps resource and HTTP planes distinct", () => {
    assert.equal(RESOURCE_METRICS.every((m) => m.plane === "resources"), true);
    assert.equal(HTTP_METRICS.every((m) => m.plane === "http"), true);
    assert.equal(RUNTIME_METRICS.length, RESOURCE_METRICS.length + HTTP_METRICS.length);
  });

  it("reads HTTP point fields", () => {
    const point = {
      t: "2026-10-09T12:00:00Z",
      rps: 1.5,
      duration_p95_ms: 42,
      status_5xx: 0,
    };
    assert.equal(runtimePointValue(point, "rps"), 1.5);
    assert.equal(runtimePointValue(point, "duration_p95_ms"), 42);
    assert.equal(runtimePointValue(point, "cpu_percent" as RuntimeMetricId), null);
  });

  it("formats duration and rate types", () => {
    assert.equal(formatRuntimeValue(12.34, "duration"), "12.3 ms");
    assert.equal(formatRuntimeValue(2.5, "rate"), "2.50/s");
  });
});
