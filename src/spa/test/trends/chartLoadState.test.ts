import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { chartLoadState } from "../../src/trends/chart/chartLoadState.ts";

describe("chartLoadState", () => {
  it("is idle when not fetching", () => {
    assert.equal(chartLoadState(false, false), "idle");
    assert.equal(chartLoadState(false, true), "idle");
  });

  it("is cold when fetching with no prior samples", () => {
    assert.equal(chartLoadState(true, false), "cold");
  });

  it("is refresh when fetching with prior samples on screen", () => {
    assert.equal(chartLoadState(true, true), "refresh");
  });
});
