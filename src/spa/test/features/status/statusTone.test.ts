import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { statusTone } from "../../../src/features/status/model/statusTone.ts";

describe("statusTone", () => {
  it("maps redeploying to warn", () => {
    assert.equal(statusTone("redeploying"), "warn");
    assert.equal(statusTone("Redeploying"), "warn");
  });

  it("keeps known intentional idle tones", () => {
    assert.equal(statusTone("scaled-to-zero"), "idle");
    assert.equal(statusTone("manual-stop"), "idle");
  });
});
