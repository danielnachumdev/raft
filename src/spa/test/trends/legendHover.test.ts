import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  ChartHoverHighlight,
  eventKindHover,
  seriesHover,
} from "../../src/trends/chart/chartHover.ts";
import {
  legendItemLabel,
  legendItemOpacity,
  legendSeriesId,
} from "../../src/trends/chart/legendHover.ts";

describe("legendSeriesId", () => {
  it("reads string dataKey from the legend payload", () => {
    assert.equal(legendSeriesId({ dataKey: "v0", value: "demo-api" }), "v0");
    assert.equal(legendSeriesId({ dataKey: 1 }), null);
    assert.equal(legendSeriesId({ value: "demo-api" }), null);
  });
});

describe("legendItemLabel", () => {
  const labels = { v0: "demo-api", v1: "demo-web" };

  it("prefers chartKey labels over the raw legend value", () => {
    assert.equal(
      legendItemLabel("v0", { dataKey: "v0", value: "v0" }, labels),
      "demo-api",
    );
    assert.equal(
      legendItemLabel("demo-web", { dataKey: "v1", value: "demo-web" }, labels),
      "demo-web",
    );
  });
});

describe("legendItemOpacity", () => {
  it("matches ChartHoverHighlight line opacity for the series", () => {
    const hover = new ChartHoverHighlight(seriesHover("v0"));
    assert.equal(legendItemOpacity({ dataKey: "v0" }, hover), 1);
    assert.ok(legendItemOpacity({ dataKey: "v1" }, hover) < 0.5);
  });

  it("dims every series while an event kind is hovered", () => {
    const hover = new ChartHoverHighlight(eventKindHover("deployment"));
    assert.ok(legendItemOpacity({ dataKey: "v0" }, hover) < 0.5);
  });

  it("stays fully opaque at rest", () => {
    const hover = new ChartHoverHighlight(null);
    assert.equal(legendItemOpacity({ dataKey: "v0" }, hover), 1);
  });
});
