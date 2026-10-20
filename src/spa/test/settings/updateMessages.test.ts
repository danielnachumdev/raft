import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  updateConfirmMessage,
  updateFailureMessage,
  updateSuccessMessage,
} from "../../src/settings/updateMessages.ts";

describe("updateConfirmMessage", () => {
  it("names the version transition and raft update path", () => {
    const msg = updateConfirmMessage("0.10.0", "0.11.0");
    assert.match(msg, /0\.10\.0/);
    assert.match(msg, /0\.11\.0/);
    assert.match(msg, /raft update/);
    assert.match(msg, /GitHub Release/);
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
      "raft is already up to date (raft 0.11.0).",
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
  it("prefixes operator-safe failure detail", () => {
    assert.equal(
      updateFailureMessage("outbound HTTPS blocked"),
      "Update failed: outbound HTTPS blocked",
    );
  });

  it("explains browser disconnect / proxy timeout", () => {
    const msg = updateFailureMessage("Failed to fetch");
    assert.match(msg, /lost the connection/i);
    assert.match(msg, /raft update/);
    assert.match(msg, /raft\.log/);
  });
});
