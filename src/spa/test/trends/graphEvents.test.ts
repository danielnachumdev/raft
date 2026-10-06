import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { GraphEvent, MetricsSeries } from "../../src/shared/api.ts";
import { mergeTimedRows } from "../../src/trends/chart/chartTimeScale.ts";
import {
  eventMarkerLabel,
  eventMarkerStroke,
  eventsForSeries,
  isRaftLevelEvent,
  seriesForEventFilter,
} from "../../src/trends/chart/graphEvents.ts";

function series(id: string, group = "demo"): MetricsSeries {
  return {
    id,
    label: id,
    kind: "container",
    role: "app",
    group,
    points: [],
  };
}

describe("isRaftLevelEvent", () => {
  it("treats global and edge services as raft-level", () => {
    assert.equal(isRaftLevelEvent({ kind: "up", ts: "t" }), true);
    assert.equal(
      isRaftLevelEvent({ kind: "stop", ts: "t", service: "raft-gate" }),
      true,
    );
    assert.equal(
      isRaftLevelEvent({ kind: "deployment", ts: "t", service: "demo-web" }),
      false,
    );
  });
});

describe("eventsForSeries", () => {
  it("keeps matching service events and always keeps raft-level", () => {
    const events: GraphEvent[] = [
      { kind: "deployment", ts: "1", service: "demo-web", label: "Deploy web" },
      { kind: "deployment", ts: "2", service: "other", label: "Deploy other" },
      { kind: "down", ts: "3", label: "Stack down" },
      { kind: "stop", ts: "4", service: "raft-router", label: "Stop router" },
    ];
    const got = eventsForSeries(events, [series("demo-web")]);
    assert.deepEqual(
      got.map((e) => e.ts),
      ["1", "3", "4"],
    );
  });
});

describe("eventMarkerStroke / label", () => {
  it("colors kinds distinctly and prefers store labels", () => {
    assert.equal(eventMarkerStroke("deployment"), "#0f6b5c");
    assert.equal(eventMarkerStroke("stop"), "#8b2e1f");
    assert.equal(eventMarkerStroke("scaling"), "#3d5a6c");
    assert.equal(eventMarkerStroke("start"), "#1a6b45");
    assert.equal(eventMarkerStroke("unknown"), "#5c564c");
    assert.equal(
      eventMarkerLabel({ kind: "deployment", ts: "t", label: " Deploy web " }),
      "Deploy web",
    );
    assert.equal(
      eventMarkerLabel({
        kind: "scaling",
        ts: "t",
        metadata: { action: "wake" },
      }),
      "Wake",
    );
  });
});

describe("series continuity with graph events", () => {
  it("does not insert null metric rows at event timestamps", () => {
    const t0 = Date.parse("2026-10-03T12:00:00.000Z");
    const t1 = t0 + 60_000;
    const eventTs = t0 + 30_000;
    const t0Iso = new Date(t0).toISOString();
    const t1Iso = new Date(t1).toISOString();
    const eventIso = new Date(eventTs).toISOString();
    const rows = mergeTimedRows([
      {
        key: "v0",
        points: [
          { ts: t0, t: t0Iso, value: 10 },
          { ts: t1, t: t1Iso, value: 20 },
        ],
      },
    ]);
    const markers = eventsForSeries(
      [{ kind: "deployment", ts: eventIso, service: "demo-web" }],
      [series("demo-web")],
    );
    assert.equal(markers.length, 1);
    assert.equal(rows.length, 2);
    assert.equal(
      rows.every((r) => typeof r.v0 === "number"),
      true,
    );
    assert.equal(
      rows.some((r) => Number(r.ts) === eventTs),
      false,
    );
  });
});

describe("seriesForEventFilter", () => {
  it("maps avg-group synthetic series back to member compose ids", () => {
    const all = [
      series("demo-api", "demo"),
      series("demo-web", "demo"),
      series("other-api", "other"),
      {
        id: "host",
        label: "Host",
        kind: "host" as const,
        role: null,
        group: null,
        points: [],
      },
    ];
    const visible = [
      {
        id: "group:demo",
        label: "demo",
        kind: "group" as const,
        role: null,
        group: "demo",
        points: [],
      },
    ];
    const filtered = seriesForEventFilter(all, visible);
    assert.deepEqual(
      filtered.map((s) => s.id).sort(),
      ["demo-api", "demo-web"],
    );
    const events: GraphEvent[] = [
      { kind: "deployment", ts: "1", service: "demo-api", label: "Deploy demo-api" },
      { kind: "scaling", ts: "2", service: "demo-web", label: "Wake demo-web" },
      { kind: "deployment", ts: "3", service: "other-api", label: "Deploy other" },
      { kind: "update", ts: "4", label: "Raft update" },
    ];
    assert.deepEqual(
      eventsForSeries(events, filtered).map((e) => e.ts),
      ["1", "2", "4"],
    );
  });
});
