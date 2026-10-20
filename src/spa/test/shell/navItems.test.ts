import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  ADD_SERVICE_NAV,
  groupNav,
  isNavActive,
  SETTINGS_NAV,
  TOPBAR_NAV,
} from "../../src/shell/navItems.ts";

const item = (id: string) => {
  const found = TOPBAR_NAV.find((n) => n.id === id);
  assert.ok(found, id);
  return found;
};

describe("isNavActive", () => {
  it("highlights Settings only on /settings itself", () => {
    assert.equal(isNavActive("/settings", SETTINGS_NAV), true);
    assert.equal(isNavActive("/settings/", SETTINGS_NAV), true);
    for (const sub of ["/settings/alerts", "/settings/notifications", "/settings/edge-access"]) {
      assert.equal(isNavActive(sub, SETTINGS_NAV), false, sub);
    }
  });

  it("keeps exactly one primary item active per configure route", () => {
    for (const path of ["/settings/alerts", "/settings/notifications", "/settings/edge-access"]) {
      const active = TOPBAR_NAV.filter((n) => isNavActive(path, n));
      assert.equal(active.length, 1, path);
      assert.equal(active[0].to, path);
    }
  });

  it("maps service and deploy pages to their parent destinations", () => {
    assert.equal(isNavActive("/service/shop-demo-api", item("nav-status")), true);
    assert.equal(isNavActive("/events", item("nav-status")), false);
    assert.equal(isNavActive("/deploy", ADD_SERVICE_NAV), true);
    assert.equal(isNavActive("/add-service", ADD_SERVICE_NAV), true);
  });
});

describe("groupNav", () => {
  it("groups consecutive items in display order", () => {
    const groups = groupNav(TOPBAR_NAV);
    assert.deepEqual(
      groups.map((g) => [g.group, g.items.map((i) => i.label)]),
      [
        ["monitor", ["Status", "Events"]],
        ["configure", ["Alerts", "Notifications", "Firewall"]],
      ],
    );
  });

  it("defaults ungrouped items to monitor and starts a new run on change", () => {
    const groups = groupNav([
      { to: "/a", label: "A", id: "a" },
      { to: "/b", label: "B", id: "b", group: "configure" },
      { to: "/c", label: "C", id: "c" },
    ]);
    assert.deepEqual(
      groups.map((g) => g.group),
      ["monitor", "configure", "monitor"],
    );
  });
});
