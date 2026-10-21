import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  dashboardRedeployTimeoutMessage,
  isAsyncDashboardRedeploy,
  isDashboardService,
  waitForDashboardReconnect,
} from "../../src/service/dashboardRedeploy.ts";

describe("dashboardRedeploy", () => {
  it("detects dashboard compose id and alias", () => {
    assert.equal(isDashboardService("raft-dashboard"), true);
    assert.equal(isDashboardService("dashboard"), true);
    assert.equal(isDashboardService("demo-api"), false);
  });

  it("requires started flag for async redeploy", () => {
    assert.equal(
      isAsyncDashboardRedeploy("raft-dashboard", "redeploy", {
        ok: true,
        action: "redeploy",
        service: "raft-dashboard",
        started: true,
      }),
      true,
    );
    assert.equal(
      isAsyncDashboardRedeploy("raft-dashboard", "redeploy", {
        ok: true,
        action: "redeploy",
        service: "raft-dashboard",
      }),
      false,
    );
    assert.equal(
      isAsyncDashboardRedeploy("demo-api", "redeploy", {
        ok: true,
        action: "redeploy",
        service: "demo-api",
        started: true,
      }),
      false,
    );
  });

  it("polls until healthy", async () => {
    let probes = 0;
    const outcome = await waitForDashboardReconnect({
      timeoutMs: 10_000,
      intervalMs: 1,
      sleep: async () => undefined,
      now: () => 0,
      probe: async () => {
        probes += 1;
        return probes >= 2;
      },
    });
    assert.equal(outcome, "ok");
    assert.equal(probes, 2);
  });

  it("times out when never healthy", async () => {
    let t = 0;
    const outcome = await waitForDashboardReconnect({
      timeoutMs: 5,
      intervalMs: 1,
      sleep: async () => undefined,
      now: () => {
        const cur = t;
        t += 3;
        return cur;
      },
      probe: async () => false,
    });
    assert.equal(outcome, "timeout");
  });

  it("keeps polling when probe throws", async () => {
    let t = 0;
    let probes = 0;
    const outcome = await waitForDashboardReconnect({
      timeoutMs: 5,
      intervalMs: 1,
      sleep: async () => undefined,
      now: () => {
        const cur = t;
        t += 3;
        return cur;
      },
      probe: async () => {
        probes += 1;
        throw new Error("network");
      },
    });
    assert.equal(outcome, "timeout");
    assert.ok(probes >= 1);
  });

  it("timeout message mentions CLI and Events", () => {
    const msg = dashboardRedeployTimeoutMessage();
    assert.match(msg, /Events/);
    assert.match(msg, /raft redeploy dashboard/);
  });
});
