import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  defaultPanelKind,
  isRenderableKind,
  panelQueryFromGraph,
  planesForQueries,
  resolvePanelView,
} from "../../src/dashboard-kit/model/query.ts";
import type { MetricsPanelQuery } from "../../src/dashboard-kit/model/types.ts";
import { defaultPanels } from "../../src/trends/dashboard/model/index.ts";
import type { MetricsSeries } from "../../src/shared/api/index.ts";
import { metricsAvailable } from "../fixtures.ts";

const T1 = "2026-10-15T12:00:00.000Z";
const T2 = "2026-10-15T12:01:00.000Z";

function series(id: string, fields: Record<string, number>[]): MetricsSeries {
  return {
    id,
    label: id,
    kind: "container",
    role: "app",
    group: "shop",
    points: fields.map((f, i) => ({ t: i === 0 ? T1 : T2, ...f })),
  };
}

describe("dashboard-kit query model", () => {
  it("lifts a graph draft into a first-class query", () => {
    const q = panelQueryFromGraph({
      metricIds: ["cpu_percent", "rps"],
      viewMode: "per_service",
      selected: ["demo-api"],
    });
    assert.deepEqual(q, {
      metricIds: ["cpu_percent", "rps"],
      viewMode: "per_service",
      selected: ["demo-api"],
    });
  });

  it("unions planes once for the shared fetch (same as #238)", () => {
    const queries = defaultPanels().map((p) => panelQueryFromGraph(p));
    assert.deepEqual(planesForQueries(queries), ["resources", "http"]);
    const httpOnly: MetricsPanelQuery[] = [
      { metricIds: ["rps"], viewMode: "per_service", selected: null },
    ];
    assert.deepEqual(planesForQueries(httpOnly), ["http"]);
  });

  it("resolves a query against shared plane data", () => {
    const data = {
      series: [
        series("demo-api", [{ cpu_percent: 10 }, { cpu_percent: 30 }]),
        series("demo-web", [{ cpu_percent: 20 }, { cpu_percent: 50 }]),
      ],
      available: [
        metricsAvailable("demo-api", "shop"),
        metricsAvailable("demo-web", "shop"),
      ],
    };
    const view = resolvePanelView(
      { metricIds: ["cpu_percent"], viewMode: "per_service", selected: ["demo-api"] },
      data,
    );
    assert.deepEqual(view.visible.map((s) => s.id), ["demo-api"]);
  });

  it("treats timeseries as the only renderable kind in v1", () => {
    assert.equal(defaultPanelKind(), "timeseries");
    assert.equal(isRenderableKind(undefined), true);
    assert.equal(isRenderableKind("timeseries"), true);
    assert.equal(isRenderableKind("stat"), false);
  });
});
