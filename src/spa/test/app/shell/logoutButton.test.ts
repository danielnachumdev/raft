import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../../src/app");

describe("LogoutButton", () => {
  it("wires oauth/password logout paths through the account menu", () => {
    const logout = readFileSync(join(root, "LogoutButton.tsx"), "utf8");
    const session = readFileSync(join(root, "useDashboardSession.ts"), "utf8");
    const userMenu = readFileSync(join(root, "UserMenu.tsx"), "utf8");
    const shell = readFileSync(join(root, "AppShell.tsx"), "utf8");
    assert.match(session, /\/api\/dashboard\/session/);
    assert.match(session, /kind === "navigate"/);
    assert.match(session, /kind === "post"/);
    assert.match(logout, /dashboard-logout/);
    assert.match(userMenu, /LogoutButton/);
    assert.match(userMenu, /dashboard-identity/);
    assert.match(shell, /UserMenu/);
  });
});
