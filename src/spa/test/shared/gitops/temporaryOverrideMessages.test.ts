import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";
import {
  TEMPORARY_OVERRIDE_TITLE,
  temporaryOverrideLead,
  temporaryOverrideSavedMessage,
  temporaryTipsDismissMessage,
  unsavedTemporaryOverrideMessage,
} from "../../../src/shared/gitops/temporaryOverrideMessages.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../..");

describe("temporaryOverrideMessages", () => {
  it("keeps temporary-change copy free of paths and sync how-to", () => {
    assert.equal(TEMPORARY_OVERRIDE_TITLE, "Temporary changes");
    for (const doc of [
      "settings.yaml",
      "firewall.yaml",
      "alerts.yaml",
      "notifications.yaml",
      "rbac.yaml",
    ] as const) {
      const lead = temporaryOverrideLead(doc);
      assert.match(lead, /this host only/i);
      assert.doesNotMatch(lead, /host\//);
      assert.doesNotMatch(lead, /GitOps/);
      assert.doesNotMatch(lead, /\.yaml/);
      const saved = temporaryOverrideSavedMessage(doc);
      assert.match(saved, /Saved/i);
      assert.doesNotMatch(saved, /host\//);
      assert.doesNotMatch(saved, /GitOps/);
    }
    assert.equal(unsavedTemporaryOverrideMessage(), "Unsaved changes");
  });

  it("tip dismiss is a short status with no config keys", () => {
    const msg = temporaryTipsDismissMessage("firewall.yaml");
    assert.match(msg, /Tip dismissed/i);
    assert.doesNotMatch(msg, /disable_tips/);
    assert.doesNotMatch(msg, /host\//);
    assert.doesNotMatch(msg, /GitOps/);
  });
});

describe("temporary-override wiring", () => {
  it("settings keep the page-level banner and override save copy", () => {
    const page = readFileSync(join(root, "src/features/settings/SettingsPage.tsx"), "utf8");
    const editor = readFileSync(
      join(root, "src/features/settings/useSettingsEditor.ts"),
      "utf8",
    );
    assert.match(page, /TemporaryOverrideBanner/);
    assert.match(page, /doc="settings\.yaml"/);
    assert.match(page, /unsavedTemporaryOverrideMessage/);
    assert.match(editor, /temporaryOverrideSavedMessage\("settings\.yaml"\)/);
  });

  it("firewall, alerts, and notifications share the banner + save warning", () => {
    const firewall = readFileSync(
      join(root, "src/features/firewall/FirewallPanel.tsx"),
      "utf8",
    );
    const alerts = readFileSync(
      join(root, "src/features/alerts/AlertsSettingsPage.tsx"),
      "utf8",
    );
    const notifications = readFileSync(
      join(root, "src/features/notifications/NotificationsSettingsPage.tsx"),
      "utf8",
    );
    assert.match(firewall, /TemporaryOverrideBanner/);
    assert.doesNotMatch(firewall, /DisableTipsCopyHint/);
    assert.match(firewall, /firewall\.yaml/);
    assert.match(alerts, /TemporaryOverrideBanner/);
    assert.doesNotMatch(alerts, /DisableTipsCopyHint/);
    assert.match(alerts, /alerts\.yaml/);
    assert.match(notifications, /TemporaryOverrideBanner/);
    assert.match(notifications, /notifications\.yaml/);
  });

  it("inspection firewall apply/remove warn temporary override", () => {
    const src = readFileSync(
      join(root, "src/features/service/httpRequests/InspectionFirewallActions.tsx"),
      "utf8",
    );
    assert.match(src, /temporaryOverrideSavedMessage\("firewall\.yaml"\)/);
    assert.doesNotMatch(src, /toast\.good\(/);
  });

  it("GitHub OAuth setup warns temporary override on settings.yaml", () => {
    const src = readFileSync(
      join(root, "src/features/deploy/oauth/OauthSetupPanel.tsx"),
      "utf8",
    );
    assert.match(src, /TemporaryOverrideBanner/);
    assert.match(src, /doc="settings\.yaml"/);
    assert.match(src, /temporaryOverrideSavedMessage\("settings\.yaml"\)/);
  });
});
