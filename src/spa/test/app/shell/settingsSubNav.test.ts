import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../../src/app");

describe("SettingsSubNav", () => {
  it("mounts under the top bar and lists settings hub sections", () => {
    const sub = readFileSync(join(root, "SettingsSubNav.tsx"), "utf8");
    const shell = readFileSync(join(root, "AppShell.tsx"), "utf8");
    const layout = readFileSync(
      join(root, "../features/settings/SettingsSectionNav.tsx"),
      "utf8",
    );
    assert.match(shell, /SettingsSubNav/);
    assert.match(sub, /SETTINGS_SECTIONS/);
    assert.match(sub, /settings-subnav/);
    assert.match(sub, /Settings pages/);
    assert.doesNotMatch(layout, /Related pages/);
    assert.doesNotMatch(layout, /SETTINGS_RELATED_PAGES/);
  });
});
