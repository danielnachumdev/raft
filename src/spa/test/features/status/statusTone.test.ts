import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { statusTone } from "../../../src/features/status/model/statusTone.ts";

describe("statusTone", () => {
  it("maps intentional operator states to idle", () => {
    assert.equal(statusTone("redeploying"), "idle");
    assert.equal(statusTone("Redeploying"), "idle");
    assert.equal(statusTone("scaled-to-zero"), "idle");
    assert.equal(statusTone("manual-stop"), "idle");
  });
});
