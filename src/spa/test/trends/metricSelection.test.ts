import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  DEFAULT_METRIC_IDS,
  metricFilterSections,
  metricsFromIds,
  planesForMetrics,
  toggleMetricId,
} from "../../src/trends/panel/metricSelection.ts";

describe("DEFAULT_METRIC_IDS", () => {
  it("defaults to CPU percent only", () => {
    assert.deepEqual(DEFAULT_METRIC_IDS, ["cpu_percent"]);
  });
});

describe("toggleMetricId", () => {
  it("adds and removes while preserving catalog order", () => {
    const withMem = toggleMetricId(["cpu_percent"], "memory_used_percent");
    assert.deepEqual(withMem, ["cpu_percent", "memory_used_percent"]);
    assert.deepEqual(toggleMetricId(withMem, "cpu_percent"), [
      "memory_used_percent",
    ]);
  });

  it("can clear down to empty", () => {
    assert.deepEqual(toggleMetricId(["cpu_percent"], "cpu_percent"), []);
  });
});

describe("planesForMetrics", () => {
  it("lists unique planes for selected metrics", () => {
    const metrics = metricsFromIds(["cpu_percent", "rps", "memory_used_percent"]);
    assert.deepEqual(planesForMetrics(metrics), ["resources", "http"]);
  });

  it("is empty when nothing selected", () => {
    assert.deepEqual(planesForMetrics([]), []);
  });
});

describe("metricFilterSections", () => {
  it("groups Resources then HTTP with type headings inside", () => {
    const sections = metricFilterSections();
    assert.deepEqual(
      sections.map((s) => s.plane),
      ["resources", "http"],
    );
    const resourceTypes = sections[0].types.map((t) => t.type.id);
    assert.ok(resourceTypes.includes("percent"));
    assert.ok(resourceTypes.includes("bytes"));
    assert.ok(resourceTypes.includes("count"));
    assert.ok(resourceTypes.includes("uptime"));
    const httpTypes = sections[1].types.map((t) => t.type.id);
    assert.deepEqual(httpTypes, ["count", "duration", "rate"]);
  });
});
