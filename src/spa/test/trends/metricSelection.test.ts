import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  DEFAULT_METRIC_IDS,
  isMetricTypeBlocked,
  MAX_METRIC_TYPES,
  metricFilterSections,
  metricsFromIds,
  planesForMetrics,
  selectedTypeIds,
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

  it("refuses a third type while allowing same-type siblings", () => {
    const twoTypes = toggleMetricId(["cpu_percent"], "status_2xx");
    assert.deepEqual(selectedTypeIds(twoTypes), ["percent", "count"]);
    assert.equal(MAX_METRIC_TYPES, 2);
    assert.equal(isMetricTypeBlocked(twoTypes, "network_rx_bytes"), true);
    assert.deepEqual(toggleMetricId(twoTypes, "network_rx_bytes"), twoTypes);
    assert.equal(isMetricTypeBlocked(twoTypes, "status_5xx"), false);
    assert.deepEqual(toggleMetricId(twoTypes, "status_5xx"), [
      "cpu_percent",
      "status_2xx",
      "status_5xx",
    ]);
    assert.equal(isMetricTypeBlocked(twoTypes, "memory_used_percent"), false);
  });

  it("unchecking frees a type slot for a new type", () => {
    const two = ["cpu_percent", "status_2xx"] as const;
    assert.equal(isMetricTypeBlocked([...two], "duration_p95_ms"), true);
    const onlyCount = toggleMetricId([...two], "cpu_percent");
    assert.deepEqual(onlyCount, ["status_2xx"]);
    assert.equal(isMetricTypeBlocked(onlyCount, "duration_p95_ms"), false);
    assert.deepEqual(toggleMetricId(onlyCount, "duration_p95_ms"), [
      "duration_p95_ms",
      "status_2xx",
    ]);
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
