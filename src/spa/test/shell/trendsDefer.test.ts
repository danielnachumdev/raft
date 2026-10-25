import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  trendsDeferDelayMs,
  trendsDeferPhase,
} from "../../src/shell/trendsDefer.ts";

describe("trendsDeferPhase", () => {
  it("stays blocked until status has painted", () => {
    assert.equal(trendsDeferPhase(false, false), "blocked");
    assert.equal(trendsDeferPhase(false, true), "blocked");
  });

  it("schedules after status then becomes ready after idle", () => {
    assert.equal(trendsDeferPhase(true, false), "scheduled");
    assert.equal(trendsDeferPhase(true, true), "ready");
  });
});

describe("trendsDeferDelayMs", () => {
  it("defers with a zero macrotask delay once status exists", () => {
    assert.equal(trendsDeferDelayMs(false), null);
    assert.equal(trendsDeferDelayMs(true), 0);
  });
});
