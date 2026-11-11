import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../../src/app");

describe("MobileNav", () => {
  it("wires hamburger menu with monitor + settings destinations", () => {
    const mobile = readFileSync(join(root, "MobileNav.tsx"), "utf8");
    const shell = readFileSync(join(root, "AppShell.tsx"), "utf8");
    const css = readFileSync(join(root, "AppShell.css"), "utf8");
    const nav = readFileSync(join(root, "navItems.ts"), "utf8");
    assert.match(shell, /MobileNav/);
    assert.match(mobile, /nav-menu-toggle/);
    assert.match(mobile, /aria-expanded/);
    assert.match(mobile, /Escape/);
    assert.match(mobile, /TOPBAR_NAV/);
    assert.match(mobile, /SETTINGS_SECTIONS/);
    assert.match(mobile, /isSettingsPath/);
    assert.doesNotMatch(mobile, /LogoutButton/);
    assert.match(nav, /nav-status/);
    assert.match(nav, /nav-edge-access/);
    assert.match(nav, /nav-notifications/);
    assert.match(nav, /nav-settings-general/);
    assert.match(css, /max-width:\s*719px/);
    assert.match(css, /\.topbar-nav\s*\{\s*display:\s*none/);
  });
});
