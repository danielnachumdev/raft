import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  updateConfirmMessage,
  updateFailureMessage,
  updateSuccessMessage,
} from "../../../src/features/settings/updateMessages.ts";

describe("updateConfirmMessage", () => {
  it("names the version transition without CLI paths", () => {
    const msg = updateConfirmMessage("0.10.0", "0.11.0");
    assert.match(msg, /0\.10\.0/);
    assert.match(msg, /0\.11\.0/);
    assert.doesNotMatch(msg, /raft update/);
    assert.doesNotMatch(msg, /install\.sh/);
  });
});

describe("updateSuccessMessage", () => {
  it("reports already current with version line", () => {
    assert.equal(
      updateSuccessMessage({
        alreadyCurrent: true,
        beforeLine: "raft 0.11.0",
        afterLine: "raft 0.11.0",
      }),
      "Already up to date (raft 0.11.0).",
    );
  });

  it("reports transition lines", () => {
    assert.equal(
      updateSuccessMessage({
        alreadyCurrent: false,
        beforeLine: "raft 0.10.0",
        afterLine: "raft 0.11.0",
      }),
      "Updated: raft 0.10.0 → raft 0.11.0",
    );
  });
});

describe("updateFailureMessage", () => {
  it("returns a generic failure without backend detail", () => {
    assert.equal(
      updateFailureMessage("outbound HTTPS blocked"),
      "Update failed. Try again later.",
    );
  });

  it("does not surface proxy or CLI how-to", () => {
    const msg = updateFailureMessage("Failed to fetch");
    assert.match(msg, /Update failed/i);
    assert.doesNotMatch(msg, /raft update/);
    assert.doesNotMatch(msg, /host log/);
  });
});
