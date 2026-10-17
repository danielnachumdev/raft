import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";
import { appResourceCache } from "../../../src/shared/cache/index.ts";

type FetchCall = { url: string; method: string };

function installFetch(handler: (url: string, init?: RequestInit) => unknown) {
  const calls: FetchCall[] = [];
  const original = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, method: (init?.method ?? "GET").toUpperCase() });
    const body = handler(url, init);
    return {
      ok: true,
      status: 200,
      json: async () => body,
    } as Response;
  }) as typeof fetch;
  return {
    calls,
    restore() {
      globalThis.fetch = original;
    },
  };
}

describe("firewall + notifications cache consumers", () => {
  afterEach(() => {
    appResourceCache.clear();
  });

  it("caches firewall document GETs until put invalidates recommendations", async () => {
    const { calls, restore } = installFetch((url, init) => {
      if (url === "/api/firewall" && (init?.method ?? "GET") === "GET") {
        return { version: 1, rules: [] };
      }
      if (url === "/api/firewall" && init?.method === "PUT") {
        return { version: 2, rules: [{ id: "r1" }] };
      }
      if (url === "/api/firewall/recommendations") {
        return { recommendations: [{ id: "rec-1" }] };
      }
      if (url === "/api/firewall/services") {
        return { services: [{ name: "demo-api" }] };
      }
      throw new Error(`unexpected ${url}`);
    });

    try {
      const fw = await import("../../../src/firewall/firewallApi.ts");
      const first = await fw.fetchFirewall();
      const second = await fw.fetchFirewall();
      assert.deepEqual(first, second);
      assert.equal(
        calls.filter((c) => c.url === "/api/firewall" && c.method === "GET")
          .length,
        1,
      );

      await fw.fetchFirewallRecommendations();
      await fw.fetchFirewallRecommendations();
      assert.equal(
        calls.filter((c) => c.url.includes("recommendations")).length,
        1,
      );

      await fw.putFirewall({ version: 1, rules: [] });
      await fw.fetchFirewallRecommendations();
      assert.equal(
        calls.filter((c) => c.url.includes("recommendations")).length,
        2,
      );
    } finally {
      restore();
    }
  });

  it("invalidates notification channels cache on create", async () => {
    let channels = [{ id: "ops", type: "webhook", enabled: true, settings: {} }];
    const { calls, restore } = installFetch((url, init) => {
      if (url === "/api/notifications/channels" && !init?.method) {
        return { enabled: true, channels };
      }
      if (url === "/api/notifications/channels" && init?.method === "GET") {
        return { enabled: true, channels };
      }
      if (url === "/api/notifications/channels" && init?.method === "POST") {
        const created = {
          id: "pager",
          type: "webhook",
          enabled: true,
          settings: {},
        };
        channels = [...channels, created];
        return created;
      }
      if (url === "/api/notifications/strategies") {
        return { strategies: [{ type_id: "webhook", label: "Webhook" }] };
      }
      throw new Error(`unexpected ${url} ${init?.method}`);
    });

    try {
      const api = await import("../../../src/notifications/notificationsApi.ts");
      await api.fetchNotificationChannels();
      await api.fetchNotificationChannels();
      assert.equal(
        calls.filter((c) => c.url === "/api/notifications/channels").length,
        1,
      );

      await api.createNotificationChannel({
        id: "pager",
        type: "webhook",
      });
      const after = await api.fetchNotificationChannels();
      assert.equal(after.channels.length, 2);
      assert.equal(
        calls.filter(
          (c) => c.url === "/api/notifications/channels" && c.method === "GET",
        ).length,
        2,
      );
    } finally {
      restore();
    }
  });
});
