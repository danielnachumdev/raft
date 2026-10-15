import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  reconcileViewConfig,
  staleSelectionMessage,
} from "../../../src/trends/views/reconcile.ts";
import type { TrendsViewConfig } from "../../../src/trends/views/types.ts";
import { defaultRangeState } from "../../../src/trends/range/index.ts";

function config(
  selected: string[] | null,
  viewMode: TrendsViewConfig["viewMode"] = "per_service",
): TrendsViewConfig {
  return {
    metricIds: ["cpu_percent"],
    viewMode,
    selected,
    range: defaultRangeState(),
  };
}

describe("reconcileViewConfig", () => {
  it("leaves selected null alone", () => {
    const got = reconcileViewConfig(config(null), ["demo-api"]);
    assert.equal(got.config.selected, null);
    assert.deepEqual(got.missingIds, []);
  });

  it("drops missing service ids and reports them", () => {
    const got = reconcileViewConfig(
      config(["demo-api", "gone-svc", "demo-web"]),
      ["demo-api", "demo-web"],
    );
    assert.deepEqual(got.config.selected, ["demo-api", "demo-web"]);
    assert.deepEqual(got.missingIds, ["gone-svc"]);
  });

  it("keeps an empty selection when every id is gone", () => {
    const got = reconcileViewConfig(config(["gone-a", "gone-b"]), ["demo-api"]);
    assert.deepEqual(got.config.selected, []);
    assert.deepEqual(got.missingIds, ["gone-a", "gone-b"]);
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
