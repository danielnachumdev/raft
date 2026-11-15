import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  clipRowsStable,
  formatTickTime,
  formatTooltipTime,
  liveNowIntervalMs,
  LIVE_TICK_MAX_MS,
  LIVE_TICK_MIN_MS,
  mergeTimedRows,
  type TimedValue,
} from "../../../src/features/trends/chart/chartTimeScale.ts";

const T0 = Date.parse("2026-10-03T18:00:00.000Z");

function pts(count: number, stepMs = 60_000): TimedValue[] {
  return Array.from({ length: count }, (_, i) => {
    const ts = T0 + i * stepMs;
    return { ts, t: new Date(ts).toISOString(), value: i };
  });
}

describe("mergeTimedRows row shape", () => {
  it("carries only ts, t and series keys (no per-row formatted label)", () => {
    const rows = mergeTimedRows([
      { key: "a", points: pts(3) },
      { key: "b", points: pts(3) },
    ]);
    for (const row of rows) {
      assert.deepEqual(Object.keys(row).sort(), ["a", "b", "t", "ts"]);
    }
  });
});

describe("clipRowsStable", () => {
  const rows = pts(10).map(({ ts, t, value }) => ({ ts, t, v: value }));
  const domain = (startIdx: number, endIdx: number) => ({
    startMs: T0 + startIdx * 60_000,
    endMs: T0 + endIdx * 60_000,
  });

  it("returns a fresh slice without a previous array", () => {
    const out = clipRowsStable(rows, domain(2, 5), null);
    assert.deepEqual(out.map((r) => r.v), [2, 3, 4, 5]);
  });

  it("keeps the previous identity while the visible slice is unchanged", () => {
    const prev = clipRowsStable(rows, domain(2, 5), null);
    const crawled = { startMs: domain(2, 5).startMs - 30_000, endMs: domain(2, 5).endMs + 30_000 };
    assert.equal(clipRowsStable(rows, crawled, prev), prev);
  });

  it("returns a new array once a sample scrolls in or out", () => {
    const prev = clipRowsStable(rows, domain(2, 5), null);
    const next = clipRowsStable(rows, domain(3, 6), prev);
    assert.notEqual(next, prev);
    assert.deepEqual(next.map((r) => r.v), [3, 4, 5, 6]);
  });

  it("returns a new array when the source rows were rebuilt", () => {
    const prev = clipRowsStable(rows, domain(2, 5), null);
    const rebuilt = rows.map((r) => ({ ...r }));
    assert.notEqual(clipRowsStable(rebuilt, domain(2, 5), prev), prev);
  });

  it("treats two empty slices as unchanged", () => {
    const prev = clipRowsStable(rows, domain(20, 30), null);
    assert.equal(clipRowsStable(rows, domain(21, 31), prev), prev);
  });
});

describe("liveNowIntervalMs", () => {
  it("scales with the window (~600 ticks per window)", () => {
    assert.equal(liveNowIntervalMs(3600), 6000);
    assert.equal(liveNowIntervalMs(900), 1500);
  });

  it("clamps to [1s, 15s]", () => {
    assert.equal(liveNowIntervalMs(60), LIVE_TICK_MIN_MS);
    assert.equal(liveNowIntervalMs(0), LIVE_TICK_MIN_MS);
    assert.equal(liveNowIntervalMs(21_600), LIVE_TICK_MAX_MS);
    assert.equal(liveNowIntervalMs(604_800), LIVE_TICK_MAX_MS);
  });
});

describe("chart time formatting parity", () => {
  const samples = [T0, T0 + 13 * 3_600_000 + 7 * 60_000, Date.parse("2026-01-31T23:59:59Z")];

  it("formatTickTime matches toLocaleTimeString / toLocaleDateString", () => {
    for (const ms of samples) {
      const d = new Date(ms);
      assert.equal(formatTickTime(ms), d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
      assert.equal(
        formatTickTime(ms, 7 * 86_400_000),
        d.toLocaleDateString([], { month: "short", day: "numeric" }),
      );
    }
    assert.equal(formatTickTime(Number.NaN), "NaN");
  });

  it("formatTooltipTime matches toLocaleString", () => {
    for (const ms of samples) {
      const iso = new Date(ms).toISOString();
      assert.equal(formatTooltipTime(iso), new Date(iso).toLocaleString());
    }
    assert.equal(formatTooltipTime("not-a-date"), "not-a-date");
  });
});
