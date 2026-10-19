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
  httpRequestsEmptyLabel,
  httpRequestsIdleHint,
  isIdleContainerStatus,
} from "../../src/service/httpRequests/emptyState.ts";
import {
  formatLatencyMs,
  formatRequestTime,
  formatRequestTimeFull,
  statusToneForCode,
} from "../../src/service/httpRequests/statusClass.ts";

describe("HTTP request empty / idle copy", () => {
  it("treats scaled-to-zero and stopped as idle containers", () => {
    assert.equal(isIdleContainerStatus("scaled-to-zero"), true);
    assert.equal(isIdleContainerStatus("not running"), true);
    assert.equal(isIdleContainerStatus("running"), false);
  });

  it("distinguishes retained-empty from ordinary empty", () => {
    assert.match(
      httpRequestsEmptyLabel({ scaledToZero: true, idleContainer: false }),
      /retained HTTP requests/,
    );
    assert.match(
      httpRequestsEmptyLabel({ scaledToZero: false, idleContainer: true }),
      /retained HTTP requests/,
    );
    assert.equal(
      httpRequestsEmptyLabel({ scaledToZero: false, idleContainer: false }),
      "No recent HTTP requests for this service.",
    );
  });

  it("scaled hint says past rows still appear", () => {
    const hint = httpRequestsIdleHint({
      scaledToZero: true,
      idleContainer: false,
    });
    assert.match(String(hint), /past edge requests still appear/i);
  });
});

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
    assert.equal(formatRequestTime("later"), "later");
    const now = Date.parse("2026-10-19T12:00:00Z");
    assert.match(formatRequestTime("2026-10-19T11:59:30Z", now), /\d{2}.\d{2}.\d{2}/);
    assert.notEqual(formatRequestTime("2026-10-10T11:59:30Z", now), formatRequestTime("2026-10-19T11:59:30Z", now));
    assert.equal(formatRequestTimeFull(null), "");
    assert.equal(formatRequestTimeFull("later"), "later");
    assert.ok(formatRequestTimeFull("2026-10-19T11:59:30Z").length > 0);
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
