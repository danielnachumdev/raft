import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  isIsolatedSeriesPoint,
  isNumericPoint,
} from "../../src/trends/chart/isolatedSeriesPoint.ts";

describe("isNumericPoint", () => {
  it("accepts finite numbers only", () => {
    assert.equal(isNumericPoint(0), true);
    assert.equal(isNumericPoint(1.5), true);
    assert.equal(isNumericPoint(null), false);
    assert.equal(isNumericPoint(undefined), false);
    assert.equal(isNumericPoint(Number.NaN), false);
    assert.equal(isNumericPoint("1"), false);
  });
});

describe("isIsolatedSeriesPoint", () => {
  const key = "v0";

  it("is true for a lone numeric sample", () => {
    const rows = [{ [key]: 3 }];
    assert.equal(isIsolatedSeriesPoint(rows, key, 0), true);
  });

  it("is false when either neighbor is numeric", () => {
    const rows = [{ [key]: 1 }, { [key]: 2 }, { [key]: 3 }];
    assert.equal(isIsolatedSeriesPoint(rows, key, 0), false);
    assert.equal(isIsolatedSeriesPoint(rows, key, 1), false);
    assert.equal(isIsolatedSeriesPoint(rows, key, 2), false);
  });

  it("treats null gaps as isolating siblings", () => {
    const rows = [
      { [key]: 1 },
      { [key]: null },
      { [key]: 2 },
      { [key]: null },
      { [key]: 3 },
      { [key]: 4 },
    ];
    assert.equal(isIsolatedSeriesPoint(rows, key, 0), true);
    assert.equal(isIsolatedSeriesPoint(rows, key, 1), false);
    assert.equal(isIsolatedSeriesPoint(rows, key, 2), true);
    assert.equal(isIsolatedSeriesPoint(rows, key, 4), false);
    assert.equal(isIsolatedSeriesPoint(rows, key, 5), false);
  });

  it("ignores other series keys when checking neighbors", () => {
    const rows = [
      { v0: 1, v1: null },
      { v0: null, v1: 9 },
      { v0: 2, v1: null },
    ];
    assert.equal(isIsolatedSeriesPoint(rows, "v0", 0), true);
    assert.equal(isIsolatedSeriesPoint(rows, "v1", 1), true);
    assert.equal(isIsolatedSeriesPoint(rows, "v0", 2), true);
  });
});
