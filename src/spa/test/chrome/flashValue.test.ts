import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  bucketIntensity,
  compareDirection,
  directionalFlash,
  magnitudeIntensity,
  parseFlashNumber,
  solidFlash,
} from "../../src/chrome/flashValue.ts";

describe("compareDirection", () => {
  it("classifies up, down, and none", () => {
    assert.equal(compareDirection(1, 2), "up");
    assert.equal(compareDirection(5, 1), "down");
    assert.equal(compareDirection(3, 3), "none");
  });

  it("treats non-finite inputs as none", () => {
    assert.equal(compareDirection(Number.NaN, 1), "none");
    assert.equal(compareDirection(1, Number.POSITIVE_INFINITY), "none");
  });
});

describe("bucketIntensity", () => {
  it("returns 0 below the first bucket", () => {
    assert.equal(bucketIntensity(0.4, [1, 5, 20]), 0);
    assert.equal(bucketIntensity(0, [1, 5]), 0);
  });

  it("steps intensity by bucket index", () => {
    assert.equal(bucketIntensity(1, [1, 5, 20]), 1 / 3);
    assert.equal(bucketIntensity(5, [1, 5, 20]), 2 / 3);
    assert.equal(bucketIntensity(20, [1, 5, 20]), 1);
    assert.equal(bucketIntensity(100, [1, 5, 20]), 1);
  });

  it("handles empty buckets", () => {
    assert.equal(bucketIntensity(10, []), 0);
  });
});

describe("magnitudeIntensity", () => {
  it("scales linearly and clamps", () => {
    assert.equal(magnitudeIntensity(0, 10), 0);
    assert.equal(magnitudeIntensity(5, 10), 0.5);
    assert.equal(magnitudeIntensity(20, 10), 1);
    assert.equal(magnitudeIntensity(5, 0), 0);
  });
});

describe("parseFlashNumber", () => {
  it("parses numbers and leading numeric prefixes", () => {
    assert.equal(parseFlashNumber(12.5), 12.5);
    assert.equal(parseFlashNumber("12.3%"), 12.3);
    assert.equal(parseFlashNumber("128 MiB / 512 MiB"), 128);
    assert.equal(parseFlashNumber("-"), null);
    assert.equal(parseFlashNumber(null), null);
  });
});

describe("solidFlash", () => {
  it("emits when the value identity changes", () => {
    const mode = solidFlash({ color: "var(--accent)", intensity: 0.4 });
    assert.equal(mode.signal(1, 1), null);
    const hit = mode.signal(1, 2);
    assert.ok(hit);
    assert.equal(hit.direction, "none");
    assert.equal(hit.color, "var(--accent)");
    assert.equal(hit.intensity, 0.4);
  });
});

describe("directionalFlash", () => {
  it("picks up/down colors and bucket intensity", () => {
    const mode = directionalFlash({ buckets: [1, 5, 10] });
    const up = mode.signal(10, 12);
    assert.ok(up);
    assert.equal(up.direction, "up");
    assert.equal(up.color, "var(--ok)");
    assert.equal(up.intensity, 1 / 3);

    const down = mode.signal(20, 5);
    assert.ok(down);
    assert.equal(down.direction, "down");
    assert.equal(down.color, "var(--danger)");
    assert.equal(down.intensity, 1);
  });

  it("uses maxAbsDelta when buckets are omitted", () => {
    const mode = directionalFlash({ maxAbsDelta: 8 });
    const hit = mode.signal(0, 4);
    assert.ok(hit);
    assert.equal(hit.intensity, 0.5);
  });

  it("honors a custom intensity callback", () => {
    const mode = directionalFlash({
      intensity: () => 0.25,
    });
    const hit = mode.signal(1, 9);
    assert.ok(hit);
    assert.equal(hit.intensity, 0.25);
  });

  it("skips equal numeric values", () => {
    const mode = directionalFlash();
    assert.equal(mode.signal("10%", "10%"), null);
  });
});
