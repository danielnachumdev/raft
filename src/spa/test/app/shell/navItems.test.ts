import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  ADD_SERVICE_NAV,
  anySettingsAllowed,
  firstSettingsPath,
  groupNav,
  isNavActive,
  isSettingsPath,
  navAllowed,
  SETTINGS_NAV,
  SETTINGS_SECTIONS,
  TOPBAR_NAV,
} from "../../../src/app/navItems.ts";

const item = (id: string) => {
  const found = [...TOPBAR_NAV, ...SETTINGS_SECTIONS].find((n) => n.id === id);
  assert.ok(found, id);
  return found;
};

describe("isNavActive", () => {
  it("highlights the Settings gear on every settings hub route", () => {
    assert.equal(isNavActive("/settings", SETTINGS_NAV), true);
    assert.equal(isNavActive("/settings/", SETTINGS_NAV), true);
    for (const sub of [
      "/settings/alerts",
      "/settings/notifications",
      "/settings/edge-access",
      "/settings/rbac",
    ]) {
      assert.equal(isNavActive(sub, SETTINGS_NAV), true, sub);
    }
  });

  it("keeps exactly one settings section active per hub route", () => {
    for (const path of [
      "/settings",
      "/settings/alerts",
      "/settings/notifications",
      "/settings/edge-access",
      "/settings/rbac",
    ]) {
      const active = SETTINGS_SECTIONS.filter((n) => isNavActive(path, n));
      assert.equal(active.length, 1, path);
      assert.equal(active[0].to, path === "/settings" ? "/settings" : path);
    }
  });

  it("maps service and deploy pages to their parent destinations", () => {
    assert.equal(isNavActive("/service/shop-demo-api", item("nav-status")), true);
    assert.equal(isNavActive("/events", item("nav-status")), false);
    assert.equal(isNavActive("/deploy", ADD_SERVICE_NAV), true);
    assert.equal(isNavActive("/add-service", ADD_SERVICE_NAV), true);
  });
});

describe("isSettingsPath", () => {
  it("matches the settings hub and no other routes", () => {
    assert.equal(isSettingsPath("/settings"), true);
    assert.equal(isSettingsPath("/settings/alerts"), true);
    assert.equal(isSettingsPath("/events"), false);
    assert.equal(isSettingsPath("/"), false);
  });
});

describe("navAllowed", () => {
  it("shows ungated items and checks the permission otherwise", () => {
    const deny = () => false;
    assert.equal(navAllowed(item("nav-status"), deny), true);
    assert.equal(navAllowed(item("nav-rbac"), deny), false);
    assert.equal(navAllowed(item("nav-settings-general"), (p) => p === "settings:read"), true);
  });
});

describe("settings hub helpers", () => {
  it("picks the first allowed settings section for the gear target", () => {
    assert.equal(firstSettingsPath(() => false), "/settings");
    assert.equal(
      firstSettingsPath((p) => p === "firewall:read"),
      "/settings/edge-access",
    );
    assert.equal(anySettingsAllowed(() => false), false);
    assert.equal(anySettingsAllowed((p) => p === "alerts:read"), true);
  });
});

describe("groupNav", () => {
  it("groups consecutive top-bar items in display order", () => {
    const groups = groupNav(TOPBAR_NAV);
    assert.deepEqual(
      groups.map((g) => [g.group, g.items.map((i) => i.label)]),
      [["monitor", ["Status", "Events"]]],
    );
  });

  it("groups settings hub sections together", () => {
    const groups = groupNav(SETTINGS_SECTIONS);
    assert.deepEqual(
      groups.map((g) => [g.group, g.items.map((i) => i.label)]),
      [["settings", ["General", "Alerts", "Notifications", "Firewall", "RBAC"]]],
    );
  });

  it("defaults ungrouped items to monitor and starts a new run on change", () => {
    const groups = groupNav([
      { to: "/a", label: "A", id: "a" },
      { to: "/b", label: "B", id: "b", group: "settings" },
      { to: "/c", label: "C", id: "c" },
    ]);
    assert.deepEqual(
      groups.map((g) => g.group),
      ["monitor", "settings", "monitor"],
    );
  });
});
