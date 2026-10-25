import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  BADGE_OVERFLOW,
  formatInboxBadge,
} from "../../src/inbox/badgeFormat.ts";

describe("formatInboxBadge", () => {
  it("hides at zero and caps above 99 as +99", () => {
    assert.equal(formatInboxBadge(0), null);
    assert.equal(formatInboxBadge(-1), null);
    assert.equal(formatInboxBadge(1), "1");
    assert.equal(formatInboxBadge(99), "99");
    assert.equal(formatInboxBadge(100), BADGE_OVERFLOW);
    assert.equal(formatInboxBadge(250), "+99");
  });
});
