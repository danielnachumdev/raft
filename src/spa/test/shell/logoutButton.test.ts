import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../src/shell");

describe("LogoutButton", () => {
  it("wires session fetch and oauth/password logout paths", () => {
    const src = readFileSync(join(root, "LogoutButton.tsx"), "utf8");
    assert.match(src, /\/api\/dashboard\/session/);
    assert.match(src, /kind === "navigate"/);
    assert.match(src, /kind === "post"/);
    assert.match(src, /dashboard-logout/);
    const shell = readFileSync(join(root, "AppShell.tsx"), "utf8");
    assert.match(shell, /LogoutButton/);
  });
});
