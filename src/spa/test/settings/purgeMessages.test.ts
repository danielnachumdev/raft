import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  purgeFailureMessage,
  purgeStartedMessage,
  purgeSuccessMessage,
} from "../../src/settings/purgeMessages.ts";

describe("purgeStartedMessage", () => {
  it("signals background start without reclaim details", () => {
    const msg = purgeStartedMessage();
    assert.match(msg, /started/i);
    assert.match(msg, /background/i);
  });
});

describe("purgeSuccessMessage", () => {
  it("reports reclaim when Docker returns a size", () => {
    assert.equal(
      purgeSuccessMessage("1.2GB"),
      "Purge finished — reclaimed 1.2GB.",
    );
  });

  it("handles empty reclaim summaries", () => {
    assert.equal(
      purgeSuccessMessage("0B"),
      "Purge finished — nothing to reclaim (0B).",
    );
    assert.equal(
      purgeSuccessMessage("-"),
      "Purge finished — nothing to reclaim (0B).",
    );
    assert.equal(
      purgeSuccessMessage(""),
      "Purge finished — nothing to reclaim (0B).",
    );
  });
});

describe("purgeFailureMessage", () => {
  it("prefixes operator-safe failure detail", () => {
    assert.equal(
      purgeFailureMessage("docker daemon unreachable"),
      "Purge failed: docker daemon unreachable",
    );
  });
});
