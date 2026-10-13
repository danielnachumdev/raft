import assert from "node:assert/strict";
import { describe, it } from "node:test";
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
