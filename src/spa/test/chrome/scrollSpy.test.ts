import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { activeSectionId } from "../../src/chrome/scrollSpy.ts";

const tops = (...values: number[]) =>
  values.map((top, i) => ({ id: `s${i}`, top }));

describe("activeSectionId", () => {
  it("picks the last section scrolled past the offset", () => {
    assert.equal(activeSectionId(tops(-400, -20, 300), 100), "s1");
    assert.equal(activeSectionId(tops(-400, 100, 300), 100), "s1");
  });

  it("falls back to the first section before any reaches the offset", () => {
    assert.equal(activeSectionId(tops(200, 600), 100), "s0");
  });

  it("selects the last section at the bottom of the page", () => {
    assert.equal(activeSectionId(tops(-400, -20, 300), 100, true), "s2");
  });

  it("returns null when there are no sections", () => {
    assert.equal(activeSectionId([], 100), null);
    assert.equal(activeSectionId([], 100, true), null);
  });
});
