import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { MetricsBounds } from "../src/shared/api.ts";
import {
  applyCustomDuration,
  clampWindowSec,
  customSeconds,
  defaultRangeState,
  isLiveQuery,
  metricsCacheKey,
  selectRangeKind,
  toQuery,
} from "../src/trends/trendsRange.ts";

const bounds: MetricsBounds = {
  retention_max_age_days: 2,
  retention_max_bytes: 100,
  available_from: "2026-10-04T12:00:00.000Z",
  earliest_ts: "2026-10-04T12:00:00.000Z",
  max_window_seconds: 2 * 86400,
};

describe("customSeconds", () => {
  it("converts units to seconds", () => {
    assert.equal(customSeconds(15, "minutes"), 900);
    assert.equal(customSeconds(2, "hours"), 7200);
    assert.equal(customSeconds(1, "days"), 86400);
  });
});

describe("clampWindowSec", () => {
  it("caps lookback at retention max window", () => {
    const got = clampWindowSec(86400 * 10, bounds);
    assert.equal(got.windowSec, 2 * 86400);
    assert.ok(got.message && got.message.includes("2 days"));
  });
});

describe("toQuery / cache / live", () => {
  it("preset sends window only", () => {
    const q = toQuery(defaultRangeState());
    assert.deepEqual(q, { window: 3600 });
    assert.equal(metricsCacheKey(q), "win:3600");
    assert.equal(isLiveQuery(q), true);
  });

  it("absolute query is not live when end is in the past", () => {
    const q = {
      window: 3600,
      start: "2026-10-05T10:00:00.000Z",
      end: "2026-10-05T11:00:00.000Z",
    };
    assert.equal(isLiveQuery(q, Date.parse("2026-10-06T12:00:00.000Z")), false);
    assert.equal(
      metricsCacheKey(q),
      "abs:2026-10-05T10:00:00.000Z:2026-10-05T11:00:00.000Z",
    );
  });
});

describe("selectRangeKind", () => {
  it("keeps presets and enters custom", () => {
    const preset = selectRangeKind(defaultRangeState(), "900", bounds);
    assert.equal(preset.mode, "preset");
    assert.equal(preset.windowSec, 900);
    assert.equal(selectRangeKind(preset, "custom", bounds).mode, "custom");
  });
});

describe("applyCustomDuration", () => {
  it("clamps custom days to retention", () => {
    const got = applyCustomDuration(defaultRangeState(), 10, "days", bounds);
    assert.equal(got.windowSec, 2 * 86400);
  });
});
