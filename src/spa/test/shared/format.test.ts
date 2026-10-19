import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  formatBytes,
  formatCount,
  formatDuration,
  formatPercent,
  relativeTime,
} from "../../src/shared/format.ts";

describe("formatBytes", () => {
  it("scales to binary units", () => {
    assert.equal(formatBytes(512), "512 B");
    assert.equal(formatBytes(1536), "1.5 KiB");
    assert.equal(formatBytes(134217728), "128 MiB");
    assert.equal(formatBytes(3 * 1024 ** 3), "3.0 GiB");
  });

  it("renders missing values as a dash", () => {
    assert.equal(formatBytes(null), "-");
    assert.equal(formatBytes(undefined), "-");
    assert.equal(formatBytes(-1), "-");
  });
});

describe("formatDuration", () => {
  it("keeps the two largest units", () => {
    assert.equal(formatDuration(93784), "1d 2h");
    assert.equal(formatDuration(3725), "1h 2m");
    assert.equal(formatDuration(42), "42s");
    assert.equal(formatDuration(0), "0s");
  });

  it("skips empty middle units", () => {
    assert.equal(formatDuration(86400 + 5), "1d 5s");
  });

  it("renders missing values as a dash", () => {
    assert.equal(formatDuration(null), "-");
  });
});

describe("formatPercent / formatCount", () => {
  it("formats finite values", () => {
    assert.equal(formatPercent(12.345), "12.3%");
    assert.equal(formatCount(12345), "12,345");
  });

  it("renders missing values as a dash", () => {
    assert.equal(formatPercent(null), "-");
    assert.equal(formatCount(undefined), "-");
  });
});

describe("relativeTime", () => {
  const now = Date.parse("2026-10-19T12:00:00Z");
  it("buckets seconds, minutes, hours, and days", () => {
    assert.equal(relativeTime("2026-10-19T11:59:58Z", now), "just now");
    assert.equal(relativeTime("2026-10-19T11:59:18Z", now), "42s ago");
    assert.equal(relativeTime("2026-10-19T11:55:00Z", now), "5m ago");
    assert.equal(relativeTime("2026-10-19T09:00:00Z", now), "3h ago");
    assert.equal(relativeTime("2026-10-17T12:00:00Z", now), "2d ago");
  });

  it("passes through unparseable input", () => {
    assert.equal(relativeTime("soon", now), "soon");
  });
});
