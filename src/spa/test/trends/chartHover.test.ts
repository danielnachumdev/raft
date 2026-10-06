import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { GraphEvent } from "../../src/shared/api.ts";
import {
  ChartHoverHighlight,
  eventKindHover,
  seriesHover,
} from "../../src/trends/chart/chartHover.ts";

describe("ChartHoverHighlight series grouping", () => {
  it("emphasizes every id in the hovered series group, not other series", () => {
    const hover = new ChartHoverHighlight(seriesHover("svc-a"));
    const ids = ["svc-a", "svc-b", "svc-a"];
    assert.deepEqual(hover.emphasizedSeriesIds(ids), ["svc-a", "svc-a"]);
    assert.equal(hover.seriesTone("svc-a"), "active");
    assert.equal(hover.seriesTone("svc-b"), "dim");
    assert.equal(hover.lineOpacity("svc-a"), 1);
    assert.ok(hover.lineOpacity("svc-b") < 0.5);
    assert.ok(hover.lineStrokeWidth("svc-a") > hover.lineStrokeWidth("svc-b"));
  });

  it("dims series while an event kind is hovered", () => {
    const hover = new ChartHoverHighlight(eventKindHover("deployment"));
    assert.equal(hover.seriesTone("svc-a"), "dim");
    assert.deepEqual(hover.emphasizedSeriesIds(["svc-a", "svc-b"]), []);
  });
});

describe("ChartHoverHighlight event-kind grouping", () => {
  it("emphasizes every event of the hovered kind across timestamps", () => {
    const events: GraphEvent[] = [
      { kind: "deployment", ts: "t1", service: "web" },
      { kind: "stop", ts: "t2", service: "web" },
      { kind: "deployment", ts: "t3", service: "api" },
    ];
    const hover = new ChartHoverHighlight(eventKindHover("deployment"));
    const kinds = events.map((e) => e.kind);
    assert.deepEqual(hover.emphasizedEventKinds(kinds), ["deployment"]);
    assert.equal(hover.eventTone("deployment"), "active");
    assert.equal(hover.eventTone("stop"), "dim");
    assert.ok(
      hover.eventStrokeWidth("deployment") > hover.eventStrokeWidth("stop"),
    );
    assert.ok(hover.eventOpacity("deployment") > hover.eventOpacity("stop"));
  });

  it("dims events while a series is hovered", () => {
    const hover = new ChartHoverHighlight(seriesHover("svc-a"));
    assert.equal(hover.eventTone("deployment"), "dim");
    assert.deepEqual(hover.emphasizedEventKinds(["deployment", "stop"]), []);
  });
});

describe("ChartHoverHighlight rest state", () => {
  it("treats all marks equally when nothing is hovered", () => {
    const hover = new ChartHoverHighlight(null);
    assert.equal(hover.seriesTone("svc-a"), "rest");
    assert.equal(hover.eventTone("deployment"), "rest");
    assert.deepEqual(hover.emphasizedSeriesIds(["a", "b"]), []);
    assert.deepEqual(hover.emphasizedEventKinds(["deployment"]), []);
    assert.equal(hover.lineStrokeWidth("a"), hover.lineStrokeWidth("b"));
  });
});
