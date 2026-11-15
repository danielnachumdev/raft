import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  intersectionObserverSupported,
  viewportVisible,
} from "../../../src/shared/chrome/viewportVisibility.ts";

describe("viewportVisible", () => {
  it("follows intersection once an element is observed", () => {
    const base = { observed: true, supported: true };
    assert.equal(viewportVisible({ ...base, intersecting: true }), true);
    assert.equal(viewportVisible({ ...base, intersecting: false }), false);
  });

  it("stays visible before the element mounts", () => {
    assert.equal(
      viewportVisible({ observed: false, supported: true, intersecting: false }),
      true,
    );
  });

  it("stays visible without IntersectionObserver", () => {
    assert.equal(
      viewportVisible({ observed: true, supported: false, intersecting: false }),
      true,
    );
  });
});

describe("intersectionObserverSupported", () => {
  it("is false under node (no DOM)", () => {
    assert.equal(intersectionObserverSupported(), false);
  });
});
