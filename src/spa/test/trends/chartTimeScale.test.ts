import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  bridgeMissingSeriesValues,
  clipRowsToDomain,
  DEFAULT_SAMPLE_INTERVAL_MS,
  GAP_INTERVAL_MULTIPLIER,
  chartEndMs,
  inferGapMs,
  mergeTimedRows,
  tickStepMs,
  timeAxisTicks,
  toEpochMs,
  windowDomain,
  withGapBreaks,
  type TimedValue,
} from "../../src/trends/chart/chartTimeScale.ts";
import { isIsolatedSeriesPoint } from "../../src/trends/chart/isolatedSeriesPoint.ts";

describe("toEpochMs", () => {
  it("parses ISO timestamps", () => {
    const ms = toEpochMs("2026-10-03T18:24:00.000Z");
    assert.equal(ms, Date.parse("2026-10-03T18:24:00.000Z"));
  });

  it("returns null for invalid input", () => {
    assert.equal(toEpochMs("not-a-date"), null);
  });
});

describe("windowDomain", () => {
  it("spans windowSeconds ending at endMs", () => {
    const end = Date.parse("2026-10-03T19:00:00.000Z");
    const domain = windowDomain(900, end);
    assert.equal(domain.endMs, end);
    assert.equal(domain.startMs, end - 900_000);
  });
});

describe("chartEndMs", () => {
  it("follows now for rolling lookback", () => {
    const now = Date.parse("2026-10-06T12:00:00.000Z");
    assert.equal(
      chartEndMs({
        rolling: true,
        nowMs: now,
        rangeEndIso: "2026-10-06T11:00:00.000Z",
      }),
      now,
    );
  });

  it("pins point-in-time to payload end", () => {
    const iso = "2026-10-05T11:00:00.000Z";
    assert.equal(
      chartEndMs({
        rolling: false,
        nowMs: Date.parse("2026-10-06T12:00:00.000Z"),
        rangeEndIso: iso,
      }),
      Date.parse(iso),
    );
  });
});

describe("clipRowsToDomain", () => {
  it("drops samples outside the window", () => {
    const end = Date.parse("2026-10-03T19:00:00.000Z");
    const domain = windowDomain(60, end);
    const rows = clipRowsToDomain(
      [
        { ts: domain.startMs - 1, v: 1 },
        { ts: domain.startMs, v: 2 },
        { ts: domain.endMs, v: 3 },
        { ts: domain.endMs + 1, v: 4 },
      ],
      domain,
    );
    assert.deepEqual(
      rows.map((r) => r.v),
      [2, 3],
    );
  });
});

describe("inferGapMs", () => {
  it("uses 2× median spacing so downsampled cadence still connects", () => {
    const t0 = Date.parse("2026-10-03T18:00:00.000Z");
    // ≥3 gaps so median 180s is trusted as cadence.
    const points: TimedValue[] = [0, 1, 2, 3].map((i) => ({
      ts: t0 + i * 180_000,
      t: `t${i}`,
      value: i,
    }));
    assert.equal(inferGapMs(points), 360_000);
  });

  it("caps short-series cadence so a lone jump still breaks", () => {
    const t0 = Date.parse("2026-10-03T18:00:00.000Z");
    const points: TimedValue[] = [
      { ts: t0, t: "a", value: 1 },
      { ts: t0 + 300_000, t: "b", value: 2 },
    ];
    assert.equal(
      inferGapMs(points),
      DEFAULT_SAMPLE_INTERVAL_MS * GAP_INTERVAL_MULTIPLIER,
    );
  });

  it("falls back to 2×60s with fewer than two samples", () => {
    assert.equal(
      inferGapMs([{ ts: 1, t: "a", value: 1 }]),
      DEFAULT_SAMPLE_INTERVAL_MS * GAP_INTERVAL_MULTIPLIER,
    );
  });
});

describe("withGapBreaks", () => {
  it("inserts a null between sparse samples (>2× interval)", () => {
    const t0 = Date.parse("2026-10-03T18:24:00.000Z");
    const t1 = Date.parse("2026-10-03T18:25:00.000Z");
    const t2 = Date.parse("2026-10-03T18:57:00.000Z");
    const out = withGapBreaks([
      { ts: t0, t: "a", value: 1 },
      { ts: t1, t: "b", value: 2 },
      { ts: t2, t: "c", value: 3 },
    ]);
    assert.equal(out.length, 4);
    assert.equal(out[0].value, 1);
    assert.equal(out[1].value, 2);
    assert.equal(out[2].value, null);
    assert.equal(out[2].ts, t1 + 1);
    assert.equal(out[3].value, 3);
    assert.ok(
      t2 - t1 >
        DEFAULT_SAMPLE_INTERVAL_MS * GAP_INTERVAL_MULTIPLIER,
    );
  });

  it("does not break adjacent minute samples", () => {
    const t0 = Date.parse("2026-10-03T18:24:00.000Z");
    const t1 = Date.parse("2026-10-03T18:25:00.000Z");
    const out = withGapBreaks([
      { ts: t0, t: "a", value: 1 },
      { ts: t1, t: "b", value: 2 },
    ]);
    assert.equal(out.length, 2);
    assert.equal(out.every((p) => p.value !== null), true);
  });
});

describe("bridgeMissingSeriesValues", () => {
  it("interpolates undefined holes between numeric samples only", () => {
    const rows: Record<string, string | number | null>[] = [
      { ts: 0, demo: 10 },
      { ts: 1 },
      { ts: 2, demo: 30 },
    ];
    bridgeMissingSeriesValues(rows, ["demo"]);
    assert.equal(rows[1].demo, 20);
  });

  it("does not fill across explicit null", () => {
    const rows: Record<string, string | number | null>[] = [
      { ts: 0, demo: 10 },
      { ts: 1, demo: null },
      { ts: 2, demo: 30 },
    ];
    bridgeMissingSeriesValues(rows, ["demo"]);
    assert.equal(rows[1].demo, null);
  });
});

describe("mergeTimedRows", () => {
  it("keeps series at true timestamps and gaps per series", () => {
    const t0 = Date.parse("2026-10-03T18:24:00.000Z");
    const t1 = Date.parse("2026-10-03T18:25:00.000Z");
    const t2 = Date.parse("2026-10-03T18:57:00.000Z");
    const rows = mergeTimedRows(
      [
        {
          key: "v0",
          points: [
            { ts: t0, t: "2026-10-03T18:24:00.000Z", value: 10 },
            { ts: t1, t: "2026-10-03T18:25:00.000Z", value: 11 },
            { ts: t2, t: "2026-10-03T18:57:00.000Z", value: 12 },
          ],
        },
        {
          key: "v1",
          points: [
            { ts: t1, t: "2026-10-03T18:25:00.000Z", value: 20 },
          ],
        },
      ],
      DEFAULT_SAMPLE_INTERVAL_MS * GAP_INTERVAL_MULTIPLIER,
    );
    const tsList = rows.map((r) => Number(r.ts));
    assert.deepEqual(tsList, [t0, t1, t1 + 1, t2]);
    assert.equal(rows[0].v0, 10);
    assert.equal(rows[1].v0, 11);
    assert.equal(rows[1].v1, 20);
    assert.equal(rows[2].v0, null);
    assert.equal(rows[3].v0, 12);
    assert.equal(rows[3].v1, undefined);
  });

  it("keeps dense multi-series connected (~60s scrapes)", () => {
    const t0 = Date.parse("2026-10-03T18:00:00.000Z");
    const points = (base: number): TimedValue[] =>
      [0, 1, 2, 3, 4].map((i) => ({
        ts: t0 + i * 60_000,
        t: `2026-10-03T18:0${i}:00.000Z`,
        value: base + i,
      }));
    const rows = mergeTimedRows([
      { key: "demo_api", points: points(10) },
      { key: "demo_web", points: points(20) },
    ]);
    assert.equal(rows.length, 5);
    for (let i = 0; i < rows.length; i++) {
      assert.equal(isIsolatedSeriesPoint(rows, "demo_api", i), false);
      assert.equal(isIsolatedSeriesPoint(rows, "demo_web", i), false);
    }
    assert.equal(countSegments(rows, "demo_api"), 1);
    assert.equal(countSegments(rows, "demo_web"), 1);
  });

  it("null on one series does not break others", () => {
    const t0 = Date.parse("2026-10-03T18:00:00.000Z");
    const rows = mergeTimedRows([
      {
        key: "demo_api",
        points: [0, 1, 2].map((i) => ({
          ts: t0 + i * 60_000,
          t: `a${i}`,
          value: 10 + i,
        })),
      },
      {
        key: "demo_idle",
        points: [
          { ts: t0, t: "b0", value: null },
          { ts: t0 + 60_000, t: "b1", value: null },
          { ts: t0 + 120_000, t: "b2", value: null },
        ],
      },
    ]);
    assert.equal(countSegments(rows, "demo_api"), 1);
    assert.equal(rows.every((r) => r.demo_idle === null), true);
  });

  it("true gap breaks only that series; neighbors stay connected", () => {
    const t0 = Date.parse("2026-10-03T18:00:00.000Z");
    const dense: TimedValue[] = [0, 1, 2, 3, 4, 5].map((i) => ({
      ts: t0 + i * 60_000,
      t: `d${i}`,
      value: i,
    }));
    // Samples at 0 and 5 min — exceeds 2×60s → sentinel on sparse only.
    const sparse: TimedValue[] = [
      { ts: t0, t: "s0", value: 100 },
      { ts: t0 + 5 * 60_000, t: "s5", value: 105 },
    ];
    const rows = mergeTimedRows(
      [
        { key: "demo_api", points: dense },
        { key: "demo_sparse", points: sparse },
      ],
      DEFAULT_SAMPLE_INTERVAL_MS * GAP_INTERVAL_MULTIPLIER,
    );
    assert.equal(countSegments(rows, "demo_api"), 1);
    assert.equal(countSegments(rows, "demo_sparse"), 2);
    assert.ok(rows.some((r) => r.demo_sparse === null));
    assert.equal(
      rows.filter((r) => r.demo_sparse === null).every(
        (r) => typeof r.demo_api === "number",
      ),
      true,
    );
  });

  it("connects downsampled cadence when gapMs is inferred", () => {
    const t0 = Date.parse("2026-10-03T18:00:00.000Z");
    // 180s spacing would exceed hard-coded 120s, but median×2 = 360s.
    const points: TimedValue[] = [0, 1, 2, 3].map((i) => ({
      ts: t0 + i * 180_000,
      t: `t${i}`,
      value: i,
    }));
    const rows = mergeTimedRows([{ key: "demo_api", points }]);
    assert.equal(rows.length, 4);
    assert.equal(countSegments(rows, "demo_api"), 1);
  });
});

function countSegments(
  rows: Record<string, string | number | null>[],
  key: string,
): number {
  let segments = 0;
  let inSeg = false;
  for (const row of rows) {
    const v = row[key];
    const numeric = typeof v === "number" && Number.isFinite(v);
    if (numeric) {
      if (!inSeg) {
        segments += 1;
        inSeg = true;
      }
    } else {
      inSeg = false;
    }
  }
  return segments;
}

describe("timeAxisTicks", () => {
  it("uses one-minute steps for a 15m window", () => {
    assert.equal(tickStepMs(900_000), 60_000);
    const end = Date.parse("2026-10-03T19:00:00.000Z");
    const domain = windowDomain(900, end);
    const ticks = timeAxisTicks(domain);
    assert.ok(ticks.length >= 14 && ticks.length <= 16);
    for (let i = 1; i < ticks.length; i++) {
      assert.equal(ticks[i] - ticks[i - 1], 60_000);
    }
  });
});
