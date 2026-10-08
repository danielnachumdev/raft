import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  filterLogLines,
  type LogFilter,
} from "../../src/logs/logFilter.ts";
import { parseLogLine } from "../../src/logs/logParse.ts";

const lines = [
  parseLogLine("app | 2024-01-01 ERROR database timeout"),
  parseLogLine("app | 2024-01-01 INFO request ok"),
  parseLogLine("app | 2024-01-01 WARN disk full"),
  parseLogLine("app | 2024-01-01 DEBUG probe"),
];

function apply(op: LogFilter["op"], values: string[]) {
  return filterLogLines(lines, { op, values }).map((l) => l.raw);
}

describe("filterLogLines", () => {
  it("returns all lines when values are empty", () => {
    assert.equal(apply("contains_any", ["", "  "]).length, 4);
  });

  it("contains all requires every needle", () => {
    assert.deepEqual(apply("contains_all", ["ERROR", "timeout"]), [
      "app | 2024-01-01 ERROR database timeout",
    ]);
    assert.deepEqual(apply("contains_all", ["ERROR", "disk"]), []);
  });

  it("contains any keeps lines with at least one needle", () => {
    assert.deepEqual(apply("contains_any", ["ERROR", "WARN"]), [
      "app | 2024-01-01 ERROR database timeout",
      "app | 2024-01-01 WARN disk full",
    ]);
  });

  it("not contains all drops only lines that include every needle", () => {
    const kept = apply("not_contains_all", ["ERROR", "timeout"]);
    assert.equal(kept.length, 3);
    assert.ok(!kept.some((l) => l.includes("ERROR database timeout")));
  });

  it("not contains any keeps lines with none of the needles", () => {
    assert.deepEqual(apply("not_contains_any", ["ERROR", "WARN"]), [
      "app | 2024-01-01 INFO request ok",
      "app | 2024-01-01 DEBUG probe",
    ]);
  });

  it("matches case-insensitively in the raw line text", () => {
    assert.deepEqual(apply("contains_any", ["error"]), [
      "app | 2024-01-01 ERROR database timeout",
    ]);
  });
});
