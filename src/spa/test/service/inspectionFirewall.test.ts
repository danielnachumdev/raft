import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { formatFirewallPort } from "../../src/firewall/firewallApi.ts";

describe("inspection firewall client helpers", () => {
  it("formats draft ports for display", () => {
    assert.equal(formatFirewallPort(443), "443");
    assert.equal(formatFirewallPort("any"), "any");
    assert.equal(formatFirewallPort(0), "any");
  });
});
