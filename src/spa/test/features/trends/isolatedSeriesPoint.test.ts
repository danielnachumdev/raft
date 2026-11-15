import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  isIsolatedSeriesPoint,
  isNumericPoint,
  isolatedPointIndices,
} from "../../../src/features/trends/chart/isolatedSeriesPoint.ts";

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

describe("isolatedPointIndices", () => {
  it("is empty for a fully connected series", () => {
    const rows = [{ v: 1 }, { v: 2 }, { v: 3 }];
    assert.equal(isolatedPointIndices(rows, "v").size, 0);
  });

  it("lists only samples with no numeric neighbors", () => {
    const rows = [
      { v: 1 },
      { v: null },
      { v: 2 },
      { v: 3 },
      { v: null },
      { v: 4 },
    ];
    assert.deepEqual([...isolatedPointIndices(rows, "v")], [0, 5]);
  });

  it("covers a single-sample series and missing keys", () => {
    assert.deepEqual([...isolatedPointIndices([{ v: 7 }], "v")], [0]);
    assert.equal(isolatedPointIndices([{ v: 7 }], "other").size, 0);
    assert.equal(isolatedPointIndices([], "v").size, 0);
  });

  it("memoizes per rows array and series key", () => {
    const rows = [{ a: 1, b: null }, { a: null, b: 2 }];
    const first = isolatedPointIndices(rows, "a");
    assert.equal(isolatedPointIndices(rows, "a"), first);
    assert.notEqual(isolatedPointIndices(rows, "b"), first);
    assert.notEqual(isolatedPointIndices([...rows], "a"), first);
  });
});
