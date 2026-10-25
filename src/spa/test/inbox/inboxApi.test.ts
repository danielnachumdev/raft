import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";
import {
  dismissInboxItem,
  fetchInbox,
  fetchInboxSummary,
  markAllInboxRead,
  markInboxItemRead,
  markInboxItemUnread,
} from "../../src/inbox/inboxApi.ts";

const calls: { url: string; method: string }[] = [];
let originalFetch: typeof fetch;

function installFetch(handler: (url: string, init?: RequestInit) => unknown) {
  originalFetch = globalThis.fetch;
  globalThis.fetch = (async (input, init) => {
    const url = String(input);
    calls.push({ url, method: (init?.method ?? "GET").toUpperCase() });
    const body = handler(url, init);
    return {
      ok: true,
      status: 200,
      json: async () => body,
    } as Response;
  }) as typeof fetch;
}

afterEach(() => {
  if (originalFetch) globalThis.fetch = originalFetch;
  calls.length = 0;
});

const sample = {
  items: [
    {
      id: "firewall-recommendation:permit-port-80",
      source: "firewall-recommendation",
      sourceItemId: "permit-port-80",
      title: "Permit edge port 80",
      summary: "Allow HTTP on the edge",
      severity: "attention",
      href: "/settings/edge-access#firewall-recommendations",
      dismissible: true,
      unread: true,
    },
  ],
  unreadCount: 1,
  badge: "1",
  badgeSemantics: "unread",
};

describe("inboxApi", () => {
  it("fetches list and summary", async () => {
    installFetch((url) => {
      if (url.endsWith("/summary")) {
        return {
          unreadCount: 1,
          badge: "1",
          badgeSemantics: "unread",
          totalCount: 1,
        };
      }
      return sample;
    });
    const listed = await fetchInbox();
    assert.equal(listed.items[0].href.includes("#firewall-recommendations"), true);
    const summary = await fetchInboxSummary();
    assert.equal(summary.unreadCount, 1);
    assert.deepEqual(
      calls.map((c) => c.url),
      ["/api/inbox", "/api/inbox/summary"],
    );
  });

  it("posts read unread mark-all and dismiss", async () => {
    installFetch(() => ({ ...sample, unreadCount: 0, badge: null }));
    const id = "firewall-recommendation:permit-port-80";
    await markInboxItemRead(id);
    await markInboxItemUnread(id);
    await markAllInboxRead();
    await dismissInboxItem(id);
    assert.deepEqual(
      calls.map((c) => [c.method, c.url]),
      [
        ["POST", `/api/inbox/items/${encodeURIComponent(id)}/read`],
        ["POST", `/api/inbox/items/${encodeURIComponent(id)}/unread`],
        ["POST", "/api/inbox/mark-all-read"],
        ["POST", `/api/inbox/items/${encodeURIComponent(id)}/dismiss`],
      ],
    );
  });

  it("surfaces API errors", async () => {
    originalFetch = globalThis.fetch;
    globalThis.fetch = (async () =>
      ({
        ok: false,
        status: 400,
        statusText: "Bad Request",
        json: async () => ({ detail: "boom" }),
      }) as Response) as typeof fetch;
    await assert.rejects(() => fetchInbox(), /boom/);
  });
});
