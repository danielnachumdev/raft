import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { RecommendationItem } from "../../src/recommendations/types.ts";

describe("recommendation item shape", () => {
  it("accepts id title summary for shared kit consumers", () => {
    const item: RecommendationItem = {
      id: "any-service-oom",
      title: "Alert when any service is OOM-killed / crash-looping",
      summary: "Watch control.container_status for every App (target *).",
      kind: "state",
    };
    assert.equal(item.id, "any-service-oom");
    assert.match(item.title, /OOM/);
  });
});
