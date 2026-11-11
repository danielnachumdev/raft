import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";

const spa = join(dirname(fileURLToPath(import.meta.url)), "../../../src");

describe("settings hub cohesion", () => {
  it("raises sticky chrome height when the settings sub-header is open", () => {
    const shell = readFileSync(join(spa, "app/AppShell.tsx"), "utf8");
    const css = readFileSync(join(spa, "app/AppShell.css"), "utf8");
    const tokens = readFileSync(join(spa, "styles/tokens.css"), "utf8");
    assert.match(shell, /dataset\.settingsHub/);
    assert.match(css, /body\[data-settings-hub\]/);
    assert.match(tokens, /--settings-subnav-height/);
    assert.match(tokens, /--topbar-brand-height/);
  });

  it("keeps draft Save on SaveBar only for General / RBAC / Firewall", () => {
    const settings = readFileSync(
      join(spa, "features/settings/SettingsPage.tsx"),
      "utf8",
    );
    const rbac = readFileSync(
      join(spa, "features/rbac/RbacSettingsPage.tsx"),
      "utf8",
    );
    const firewall = readFileSync(
      join(spa, "features/firewall/FirewallPanel.tsx"),
      "utf8",
    );
    assert.match(settings, /title="General"/);
    assert.match(settings, /settings-save-bar/);
    assert.doesNotMatch(settings, /id="settings-save"/);
    assert.match(rbac, /rbac-save-bar/);
    assert.doesNotMatch(rbac, /id="rbac-save"/);
    assert.match(rbac, /SettingsFormSkeleton/);
    assert.doesNotMatch(firewall, /id="firewall-save"/);
    assert.match(firewall, /firewall-dirty/);
  });

  it("shares ModeSwitch for form/YAML editors", () => {
    const mode = readFileSync(join(spa, "shared/chrome/ModeSwitch.tsx"), "utf8");
    const settings = readFileSync(
      join(spa, "features/settings/SettingsPage.tsx"),
      "utf8",
    );
    const rbac = readFileSync(
      join(spa, "features/rbac/RbacSettingsPage.tsx"),
      "utf8",
    );
    assert.match(mode, /export function ModeSwitch/);
    assert.match(settings, /from "..\/..\/shared\/chrome\/ModeSwitch"/);
    assert.match(rbac, /from "..\/..\/shared\/chrome\/ModeSwitch"/);
  });
});
