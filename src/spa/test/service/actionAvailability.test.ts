import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { actionAvailability } from "../../src/service/actionAvailability.ts";

describe("actionAvailability", () => {
  it("disables up for a running service", () => {
    const a = actionAvailability("running");
    assert.equal(a.up.enabled, false);
    assert.equal(a.down.enabled, true);
    assert.equal(a.redeploy.enabled, true);
  });

  it("disables down for stopped services", () => {
    for (const status of ["exited", "Not running", "dead", "created"]) {
      const a = actionAvailability(status);
      assert.equal(a.down.enabled, false, status);
      assert.equal(a.up.enabled, true, status);
    }
  });

  it("keeps everything enabled for transitional or unknown states", () => {
    for (const status of ["scaled-to-zero", "restarting", "unknown", "", null]) {
      const a = actionAvailability(status);
      assert.equal(a.up.enabled, true, String(status));
      assert.equal(a.down.enabled, true, String(status));
    }
  });
});
