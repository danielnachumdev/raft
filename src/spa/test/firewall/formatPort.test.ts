import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { formatFirewallPort } from "../../src/firewall/firewallApi.ts";

describe("firewall port display", () => {
  it("formats any and numeric ports", () => {
    assert.equal(formatFirewallPort("any"), "any");
    assert.equal(formatFirewallPort(0), "any");
    assert.equal(formatFirewallPort(443), "443");
  });
});
