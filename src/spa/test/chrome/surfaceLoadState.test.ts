import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  showSkeleton,
  surfaceLoadState,
} from "../../src/chrome/skeleton/surfaceLoadState.ts";

describe("surfaceLoadState", () => {
  it("is idle when not fetching", () => {
    assert.equal(surfaceLoadState(false, false), "idle");
    assert.equal(surfaceLoadState(false, true), "idle");
  });

  it("is cold when fetching with no prior data", () => {
    assert.equal(surfaceLoadState(true, false), "cold");
  });

  it("is refresh when fetching with prior data on screen", () => {
    assert.equal(surfaceLoadState(true, true), "refresh");
  });
});

describe("showSkeleton", () => {
  it("only shows skeleton on cold load", () => {
    assert.equal(showSkeleton(true, false), true);
    assert.equal(showSkeleton(true, true), false);
    assert.equal(showSkeleton(false, false), false);
    assert.equal(showSkeleton(false, true), false);
  });
});
