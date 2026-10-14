import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { actionAvailability } from "../../src/service/actionAvailability.ts";

describe("actionAvailability", () => {
  it("disables start for a running service", () => {
    const a = actionAvailability("running");
    assert.equal(a.start.enabled, false);
    assert.equal(a.stop.enabled, true);
    assert.equal(a.redeploy.enabled, true);
  });

  it("disables stop for stopped services", () => {
    for (const status of ["exited", "Not running", "dead", "created"]) {
      const a = actionAvailability(status);
      assert.equal(a.stop.enabled, false, status);
      assert.equal(a.start.enabled, true, status);
    }
  });

  it("keeps everything enabled for transitional or unknown states", () => {
    for (const status of ["scaled-to-zero", "restarting", "unknown", "", null]) {
      const a = actionAvailability(status);
      assert.equal(a.start.enabled, true, String(status));
      assert.equal(a.stop.enabled, true, String(status));
    }
  });
});
