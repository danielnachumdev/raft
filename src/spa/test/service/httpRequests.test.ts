import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  applyColumnResize,
  clampColumnWidth,
  defaultColumnWidths,
  MAX_COLUMN_WIDTH,
  MIN_COLUMN_WIDTH,
  tableMinWidth,
} from "../../src/service/httpRequests/columnResize.ts";
import {
  formatLatencyMs,
  formatRequestTime,
  statusToneForCode,
} from "../../src/service/httpRequests/statusClass.ts";

describe("HTTP request inspection helpers", () => {
  it("tones status classes", () => {
    assert.equal(statusToneForCode(200), "ok");
    assert.equal(statusToneForCode(301), "warn");
    assert.equal(statusToneForCode(404), "bad");
    assert.equal(statusToneForCode(500), "bad");
    assert.equal(statusToneForCode(100), "muted");
  });

  it("formats latency and missing time", () => {
    assert.equal(formatLatencyMs(1.2), "1.2 ms");
    assert.equal(formatLatencyMs(42.6), "43 ms");
    assert.equal(formatRequestTime(null), "—");
  });
});

describe("HTTP request column resize helpers", () => {
  it("clamps widths to min and max", () => {
    assert.equal(clampColumnWidth(10), MIN_COLUMN_WIDTH);
    assert.equal(clampColumnWidth(9000), MAX_COLUMN_WIDTH);
    assert.equal(clampColumnWidth(120.4), 120);
  });

  it("applies horizontal drag delta to one column", () => {
    const start = defaultColumnWidths();
    const next = applyColumnResize(start, "ua", start.ua, 80);
    assert.equal(next.ua, start.ua + 80);
    assert.equal(next.path, start.path);
  });

  it("sums column widths for table min-width / horizontal scroll", () => {
    const widths = defaultColumnWidths();
    assert.equal(tableMinWidth(widths), Object.values(widths).reduce((a, b) => a + b, 0));
  });
});
