import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { STATUS_POLL_MS } from "../../src/shared/api.ts";

describe("STATUS_POLL_MS", () => {
  it("keeps out-of-band apply lag within a few seconds", () => {
    assert.equal(STATUS_POLL_MS, 2000);
    assert.ok(STATUS_POLL_MS <= 5000);
  });
});
