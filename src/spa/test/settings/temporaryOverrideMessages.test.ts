import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";
import {
  TEMPORARY_OVERRIDE_TITLE,
  temporaryOverrideGuidance,
  temporaryOverrideLead,
  temporaryOverrideSavedMessage,
} from "../../src/settings/temporaryOverrideMessages.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "../..");

describe("temporaryOverrideMessages", () => {
  it("names a temporary host override wiped by the next GitOps sync", () => {
    assert.equal(TEMPORARY_OVERRIDE_TITLE, "Temporary host override");
    const lead = temporaryOverrideLead();
    assert.match(lead, /temporary|live testing/i);
    assert.match(lead, /host\/settings\.yaml/);
    assert.match(lead, /GitOps/);
    assert.match(lead, /wipe|replace/i);
    const guidance = temporaryOverrideGuidance();
    assert.match(guidance, /vpsctl|GitOps repo/i);
    assert.match(guidance, /RBAC/);
    assert.match(guidance, /click-ops/i);
  });

  it("warns on save that GitOps sync will replace the file", () => {
    const msg = temporaryOverrideSavedMessage();
    assert.match(msg, /Temporary host override saved/i);
    assert.match(msg, /GitOps sync/);
    assert.match(msg, /host\/settings\.yaml/);
  });
});

describe("Settings temporary-override wiring", () => {
  it("shows one page-level banner and uses override copy on save/dirty", () => {
    const page = readFileSync(join(root, "src/settings/SettingsPage.tsx"), "utf8");
    const banner = readFileSync(
      join(root, "src/settings/TemporaryOverrideBanner.tsx"),
      "utf8",
    );
    const editor = readFileSync(
      join(root, "src/settings/useSettingsEditor.ts"),
      "utf8",
    );
    assert.match(page, /TemporaryOverrideBanner/);
    assert.match(page, /temporary host overrides/i);
    assert.match(page, /Unsaved temporary override/);
    assert.match(banner, /id="settings-temp-override"/);
    assert.match(banner, /TEMPORARY_OVERRIDE_TITLE/);
    assert.match(editor, /temporaryOverrideSavedMessage/);
  });
});
