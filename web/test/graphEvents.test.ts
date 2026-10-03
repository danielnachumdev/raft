import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { GraphEvent, MetricsSeries } from "../src/api.ts";
import {
  eventMarkerLabel,
  eventMarkerStroke,
  eventsForSeries,
  isRaftLevelEvent,
  seriesForEventFilter,
  withEventRows,
} from "../src/graphEvents.ts";

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

describe("withEventRows", () => {
  it("inserts epoch rows for event timestamps missing from samples", () => {
    const rows = withEventRows(
      [{ t: "2026-10-03T12:00:00.000Z", ts: Date.parse("2026-10-03T12:00:00.000Z"), label: "a", v: 1 }],
      [{ kind: "up", ts: "2026-10-03T12:30:00.000Z" }],
      (t, label) => ({ t, ts: Date.parse(t), label, v: null }),
    );
    assert.equal(rows.length, 2);
    assert.equal(rows[1].t, "2026-10-03T12:30:00.000Z");
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
