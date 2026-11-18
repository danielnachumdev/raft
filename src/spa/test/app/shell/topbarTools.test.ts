import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../../src/app");

describe("topbar tools", () => {
  it("keeps Settings gear as the rightmost tool without a hamburger menu", () => {
    const shell = readFileSync(join(root, "AppShell.tsx"), "utf8");
    const css = readFileSync(join(root, "AppShell.css"), "utf8");
    assert.doesNotMatch(shell, /MobileNav/);
    assert.doesNotMatch(shell, /nav-menu-toggle/);
    assert.match(shell, /SETTINGS_NAV\.id/);
    assert.match(shell, /<UserMenu \/>/);
    const userMenuAt = shell.indexOf("<UserMenu />");
    const settingsAt = shell.indexOf("id={SETTINGS_NAV.id}");
    assert.ok(userMenuAt > 0 && settingsAt > userMenuAt);
    assert.doesNotMatch(css, /\.topbar-nav\s*\{\s*display:\s*none/);
    assert.doesNotMatch(css, /data-mobile-nav-open/);
  });
});
