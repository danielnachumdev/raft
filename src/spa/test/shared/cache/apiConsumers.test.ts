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

describe("github + service + exports cache consumers", () => {
  afterEach(() => {
    appResourceCache.clear();
  });

  it("caches github session/config/repos and invalidates repos on select", async () => {
    let active = "acct-a";
    const { calls, restore } = installFetch((url, init) => {
      if (url === "/api/github/session" && (init?.method ?? "GET") === "GET") {
        return { authenticated: true, active_account_id: active, accounts: [] };
      }
      if (url === "/api/github/config") {
        return { configured: true, clientId: "cid" };
      }
      if (url === "/api/github/repos") {
        return { repos: [{ full_name: `org/${active}` }] };
      }
      if (url === "/api/github/accounts/select" && init?.method === "POST") {
        active = "acct-b";
        return { authenticated: true, active_account_id: active, accounts: [] };
      }
      throw new Error(`unexpected ${url} ${init?.method}`);
    });

    try {
      const gh = await import("../../../src/deploy/github/client.ts");
      await gh.fetchGithubSession();
      await gh.fetchGithubSession();
      await gh.fetchGithubConfig();
      await gh.fetchGithubConfig();
      await gh.fetchGithubRepos();
      await gh.fetchGithubRepos();
      assert.equal(
        calls.filter((c) => c.url === "/api/github/session" && c.method === "GET")
          .length,
        1,
      );
      assert.equal(
        calls.filter((c) => c.url === "/api/github/config" && c.method === "GET")
          .length,
        1,
      );
      assert.equal(
        calls.filter((c) => c.url === "/api/github/repos" && c.method === "GET")
          .length,
        1,
      );

      await gh.selectGithubAccount("acct-b");
      const repos = await gh.fetchGithubRepos();
      assert.equal(repos[0]?.full_name, "org/acct-b");
      assert.equal(
        calls.filter((c) => c.url === "/api/github/repos" && c.method === "GET")
          .length,
        2,
      );
    } finally {
      restore();
    }
  });

  it("caches service detail until lifecycle action invalidates", async () => {
    let status = "running";
    const { calls, restore } = installFetch((url, init) => {
      if (url === "/api/service/demo-api" && (init?.method ?? "GET") === "GET") {
        return {
          host: { hostname: "demo" },
          container: { service: "demo-api", status, role: "app" },
          presentation: { service: "demo-api", name: "demo-api", status },
        };
      }
      if (url === "/api/service/demo-api/stop" && init?.method === "POST") {
        status = "exited";
        return { ok: true, action: "stop", service: "demo-api" };
      }
      throw new Error(`unexpected ${url}`);
    });

    try {
      const svc = await import("../../../src/shared/api/service.ts");
      const first = await svc.fetchService("demo-api");
      const second = await svc.fetchService("demo-api");
      assert.equal(first.container.status, "running");
      assert.equal(second.container.status, "running");
      assert.equal(
        calls.filter((c) => c.url === "/api/service/demo-api" && c.method === "GET")
          .length,
        1,
      );

      await svc.postServiceAction("demo-api", "stop");
      const after = await svc.fetchService("demo-api");
      assert.equal(after.container.status, "exited");
      assert.equal(
        calls.filter((c) => c.url === "/api/service/demo-api" && c.method === "GET")
          .length,
        2,
      );
    } finally {
      restore();
    }
  });

  it("caches export catalog GETs across loadExportCatalog calls", async () => {
    const { calls, restore } = installFetch((url) => {
      if (url === "/api/exports") {
        return {
          logs: [{ id: "txt", label: "Plain text", media_type: "text/plain", suffix: "txt" }],
          metrics: [],
        };
      }
      throw new Error(`unexpected ${url}`);
    });

    try {
      const catalog = await import("../../../src/export/catalog.ts");
      const first = await catalog.loadExportCatalog();
      const second = await catalog.loadExportCatalog();
      assert.deepEqual(first, second);
      assert.equal(calls.filter((c) => c.url === "/api/exports").length, 1);
    } finally {
      restore();
    }
  });
});
