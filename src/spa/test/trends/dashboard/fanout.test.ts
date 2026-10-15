import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  defaultPanels,
  graphSubtitle,
  graphTitle,
  graphView,
  headlineStat,
  planesForGraphs,
  seriesPalette,
  type TrendsGraphDraft,
} from "../../../src/trends/dashboard/model/index.ts";
import { metricsFromIds } from "../../../src/trends/panel/metricSelection.ts";
import type { MetricsSeries } from "../../../src/shared/api/index.ts";
import { metricsAvailable } from "../../fixtures.ts";

const T1 = "2026-10-15T12:00:00.000Z";
const T2 = "2026-10-15T12:01:00.000Z";

function series(id: string, group: string | null, fields: Record<string, number>[]): MetricsSeries {
  return {
    id,
    label: id,
    kind: id === "host" ? "host" : "container",
    role: id === "host" ? "host" : "app",
    group,
    points: fields.map((f, i) => ({ t: i === 0 ? T1 : T2, ...f })),
  };
}

const data = {
  series: [
    series("demo-api", "shop", [{ cpu_percent: 10, rps: 2 }, { cpu_percent: 30, rps: 4 }]),
    series("demo-web", "shop", [{ cpu_percent: 20, rps: 1 }, { cpu_percent: 50, rps: 3 }]),
    series("host", null, [{ cpu_percent: 5 }]),
  ],
  available: [
    metricsAvailable("demo-web", "shop"),
    metricsAvailable("demo-api", "shop"),
    metricsAvailable("host", null, "host"),
  ],
};

const graph = (over: Partial<TrendsGraphDraft>): TrendsGraphDraft => ({
  title: "",
  metricIds: ["cpu_percent"],
  viewMode: "per_service",
  selected: null,
  size: "half",
  ...over,
});

describe("shared fetch fan-out", () => {
  it("needs both planes for the default layout (one request each)", () => {
    assert.deepEqual(planesForGraphs(defaultPanels()), ["resources", "http"]);
  });

  it("asks only for planes in use, resources when nothing is plotted", () => {
    assert.deepEqual(planesForGraphs([graph({ metricIds: ["rps"] })]), ["http"]);
    assert.deepEqual(planesForGraphs([]), ["resources"]);
    assert.deepEqual(planesForGraphs([graph({ metricIds: [] })]), ["resources"]);
  });

  it("filters one shared payload differently per graph", () => {
    const cpu = graphView(graph({}), data);
    const rps = graphView(graph({ metricIds: ["rps"] }), data);
    const one = graphView(graph({ selected: ["demo-web"] }), data);
    assert.deepEqual(cpu.visible.map((s) => s.id).sort(), ["demo-api", "demo-web", "host"]);
    assert.deepEqual(rps.visible.map((s) => s.id).sort(), ["demo-api", "demo-web"]);
    assert.deepEqual(one.visible.map((s) => s.id), ["demo-web"]);
  });

  it("builds group series for group views", () => {
    const got = graphView(graph({ viewMode: "avg_group" }), data);
    assert.deepEqual(got.pickerIds, ["shop"]);
    assert.deepEqual(got.visible.map((s) => s.id), ["group:shop"]);
  });

  it("gives each service the same color slot on every graph", () => {
    const palette = seriesPalette(data.available);
    assert.equal(palette.get("demo-api"), 0);
    assert.equal(palette.get("demo-web"), 1);
    assert.equal(palette.get("group:shop"), 0);
  });
});

describe("graph header copy", () => {
  it("derives a title from metric labels when blank", () => {
    assert.equal(graphTitle(graph({ title: "  CPU " })), "CPU");
    assert.equal(
      graphTitle(graph({ metricIds: ["network_rx_bytes", "network_tx_bytes"] })),
      "Network RX · Network TX",
    );
    assert.equal(graphTitle(graph({ metricIds: [] })), "Untitled graph");
  });

  it("summarises view mode and selection", () => {
    assert.equal(graphSubtitle(graph({}), 3, 3, false), "Per service · all services");
    assert.equal(
      graphSubtitle(graph({ viewMode: "per_group", selected: ["shop"] }), 1, 2, true),
      "Per group · 1 of 2 groups",
    );
  });
});

describe("headlineStat", () => {
  const visible = data.series.slice(0, 2);
  const rps = metricsFromIds(["rps"]);
  it("shows the worst series for percent metrics", () => {
    const got = headlineStat(visible, metricsFromIds(["cpu_percent"]), false)!;
    assert.equal(got.value, 50);
    assert.equal(got.how, "max");
  });

  it("sums additive metrics and averages avg views", () => {
    assert.equal(headlineStat(visible, rps, false)!.value, 7);
    assert.equal(headlineStat(visible, rps, true)!.how, "avg");
    assert.equal(headlineStat(visible, rps, true)!.value, 3.5);
  });

  it("folds same-type metric pairs, uses the first of mixed types", () => {
    const errors = [
      series("demo-api", null, [{ status_4xx: 3, status_5xx: 2 }]),
      series("demo-web", null, [{ status_4xx: 1, status_5xx: 0 }]),
    ];
    const pair = metricsFromIds(["status_4xx", "status_5xx"]);
    assert.equal(headlineStat(errors, pair, false)!.value, 6);
    const mixed = metricsFromIds(["cpu_percent", "rps"]);
    assert.deepEqual(headlineStat(visible, mixed, false)!.metrics, [mixed[0]]);
  });

  it("does not double-count the HTTP edge total", () => {
    const edge = { ...series("edge", "raft", [{ rps: 7 }]), role: "edge", kind: "http" };
    assert.equal(headlineStat([...visible, edge], rps, false)!.value, 7);
    assert.equal(headlineStat([edge], rps, false)!.value, 7);
  });

  it("returns null without samples or metrics", () => {
    assert.equal(headlineStat([], rps, false), null);
    assert.equal(headlineStat(visible, [], false), null);
  });
});
