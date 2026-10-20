import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  clampSpan,
  GRID_COLUMNS,
  gridCellClass,
  sizeToSpan,
  SPAN_FULL,
  SPAN_HALF,
  spanToSize,
} from "../../src/dashboard-kit/model/layout.ts";

describe("dashboard-kit layout", () => {
  it("maps half/full onto a 12-column span", () => {
    assert.equal(sizeToSpan("half"), SPAN_HALF);
    assert.equal(sizeToSpan("full"), SPAN_FULL);
    assert.equal(SPAN_HALF, 6);
    assert.equal(SPAN_FULL, GRID_COLUMNS);
  });

  it("collapses spans back to v1 CSS tokens", () => {
    assert.equal(spanToSize(1), "half");
    assert.equal(spanToSize(6), "half");
    assert.equal(spanToSize(7), "half");
    assert.equal(spanToSize(12), "full");
    assert.equal(gridCellClass("half"), "is-half");
    assert.equal(gridCellClass("full"), "is-full");
  });

  it("clamps invalid spans", () => {
    assert.equal(clampSpan(0), 1);
    assert.equal(clampSpan(99), 12);
    assert.equal(clampSpan(Number.NaN), SPAN_HALF);
  });
});
