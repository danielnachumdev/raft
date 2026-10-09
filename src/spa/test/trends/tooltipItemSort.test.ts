import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  tooltipItemMagnitude,
  tooltipItemSortKey,
  type TooltipSortItem,
} from "../../src/trends/chart/tooltipItemSort.ts";

function sortedNames(items: TooltipSortItem[]): string[] {
  return [...items]
    .sort((a, b) => tooltipItemSortKey(a).localeCompare(tooltipItemSortKey(b)))
    .map((i) => String(i.name));
}

describe("tooltipItemSortKey", () => {
  it("orders CPU % by magnitude desc with name tie-break", () => {
    const items: TooltipSortItem[] = [
      { value: 10.2, name: "alpha" },
      { value: 80.5, name: "bravo" },
      { value: 40.1, name: "charlie" },
      { value: 40.1, name: "alpha-dup" },
    ];
    assert.deepEqual(sortedNames(items), [
      "bravo",
      "alpha-dup",
      "charlie",
      "alpha",
    ]);
  });

  it("orders Network RX byte magnitudes desc (regression for 1e9 ceiling)", () => {
    const items: TooltipSortItem[] = [
      { value: 2_000_000, name: "smallish" },
      { value: 3_000_000, name: "bigger" },
      { value: 500, name: "tiny" },
      { value: 50_000_000, name: "huge" },
    ];
    assert.deepEqual(sortedNames(items), [
      "huge",
      "bigger",
      "smallish",
      "tiny",
    ]);
  });

  it("orders seconds and count units by magnitude", () => {
    const seconds: TooltipSortItem[] = [
      { value: 90, name: "a" },
      { value: 3600, name: "b" },
      { value: 12, name: "c" },
    ];
    assert.deepEqual(sortedNames(seconds), ["b", "a", "c"]);
    const counts: TooltipSortItem[] = [
      { value: 3, name: "x" },
      { value: 100, name: "y" },
      { value: 20, name: "z" },
    ];
    assert.deepEqual(sortedNames(counts), ["y", "z", "x"]);
  });

  it("reads the first value from array payloads", () => {
    assert.equal(tooltipItemMagnitude({ value: [1_024, 2_048] }), 1024);
    const items: TooltipSortItem[] = [
      { value: [100], name: "low" },
      { value: [900], name: "high" },
    ];
    assert.deepEqual(sortedNames(items), ["high", "low"]);
  });

  it("sorts non-finite magnitudes last", () => {
    const items: TooltipSortItem[] = [
      { value: "n/a", name: "bad" },
      { value: 5, name: "ok" },
      { value: undefined, name: "missing" },
    ];
    assert.deepEqual(sortedNames(items), ["ok", "bad", "missing"]);
  });
});
