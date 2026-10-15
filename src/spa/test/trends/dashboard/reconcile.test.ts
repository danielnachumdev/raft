import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  reconcileSelection,
  staleSelectionMessage,
} from "../../../src/trends/dashboard/model/reconcile.ts";
import { graphView } from "../../../src/trends/dashboard/model/fanout.ts";
import type { TrendsGraphDraft } from "../../../src/trends/dashboard/model/types.ts";
import { metricsAvailable, metricsSeries } from "../../fixtures.ts";

describe("reconcileSelection", () => {
  it("leaves selected null alone", () => {
    const got = reconcileSelection(null, ["demo-api"]);
    assert.equal(got.selected, null);
    assert.deepEqual(got.missingIds, []);
  });

  it("drops missing service ids and reports them", () => {
    const got = reconcileSelection(
      ["demo-api", "gone-svc", "demo-web"],
      ["demo-api", "demo-web"],
    );
    assert.deepEqual(got.selected, ["demo-api", "demo-web"]);
    assert.deepEqual(got.missingIds, ["gone-svc"]);
  });

  it("keeps an empty selection when every id is gone", () => {
    const got = reconcileSelection(["gone-a", "gone-b"], ["demo-api"]);
    assert.deepEqual(got.selected, []);
    assert.deepEqual(got.missingIds, ["gone-a", "gone-b"]);
  });

  it("does not flag anything before the catalog has loaded", () => {
    const got = reconcileSelection(["demo-api"], []);
    assert.deepEqual(got.selected, ["demo-api"]);
    assert.deepEqual(got.missingIds, []);
  });
});

describe("per-graph stale reconcile", () => {
  const graph = (
    selected: string[] | null,
    viewMode: TrendsGraphDraft["viewMode"] = "per_service",
  ): TrendsGraphDraft => ({
    title: "",
    metricIds: ["cpu_percent"],
    viewMode,
    selected,
    size: "half",
  });
  const t = "2026-10-15T12:00:00.000Z";
  const data = {
    series: [metricsSeries("demo-api", "shop", [{ t, cpu: 10 }])],
    available: [metricsAvailable("demo-api", "shop")],
  };

  it("reports stale ids on one graph without touching the others", () => {
    const stale = graphView(graph(["demo-api", "gone-svc"]), data);
    const fine = graphView(graph(null), data);
    assert.equal(stale.staleMessage, "1 saved service no longer available.");
    assert.deepEqual(stale.activeIds, ["demo-api"]);
    assert.equal(fine.staleMessage, null);
  });

  it("reconciles group graphs against group ids", () => {
    const got = graphView(graph(["shop", "old-group"], "per_group"), data);
    assert.equal(got.staleMessage, "1 saved group no longer available.");
    assert.deepEqual(got.visible.map((s) => s.id), ["group:shop"]);
  });
});

describe("staleSelectionMessage", () => {
  it("returns null when nothing is missing", () => {
    assert.equal(staleSelectionMessage([], false), null);
  });

  it("names services or groups in the notice", () => {
    assert.match(staleSelectionMessage(["a"], false)!, /1 saved service/);
    assert.match(staleSelectionMessage(["a", "b"], true)!, /2 saved groups/);
  });
});
