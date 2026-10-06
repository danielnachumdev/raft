import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  clipRowsToDomain,
  DEFAULT_SAMPLE_INTERVAL_MS,
  GAP_INTERVAL_MULTIPLIER,
  chartEndMs,
  mergeTimedRows,
  tickStepMs,
  timeAxisTicks,
  toEpochMs,
  windowDomain,
  withGapBreaks,
} from "../../src/trends/chart/chartTimeScale.ts";

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

describe("mergeTimedRows", () => {
  it("keeps series at true timestamps and gaps per series", () => {
    const t0 = Date.parse("2026-10-03T18:24:00.000Z");
    const t1 = Date.parse("2026-10-03T18:25:00.000Z");
    const t2 = Date.parse("2026-10-03T18:57:00.000Z");
    const rows = mergeTimedRows([
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
    ]);
    const tsList = rows.map((r) => Number(r.ts));
    assert.deepEqual(tsList, [t0, t1, t1 + 1, t2]);
    assert.equal(rows[0].v0, 10);
    assert.equal(rows[1].v0, 11);
    assert.equal(rows[1].v1, 20);
    assert.equal(rows[2].v0, null);
    assert.equal(rows[3].v0, 12);
    assert.equal(rows[3].v1, undefined);
  });
});

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
