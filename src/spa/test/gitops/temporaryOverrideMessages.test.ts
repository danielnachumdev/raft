import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";
import {
  TEMPORARY_OVERRIDE_TITLE,
  disableTipsYamlSnippet,
  temporaryOverrideGuidance,
  temporaryOverrideLead,
  temporaryOverrideSavedMessage,
  unsavedTemporaryOverrideMessage,
} from "../../src/gitops/temporaryOverrideMessages.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "../..");

describe("temporaryOverrideMessages", () => {
  it("names a temporary host override wiped by the next GitOps sync", () => {
    assert.equal(TEMPORARY_OVERRIDE_TITLE, "Temporary host override");
    for (const doc of [
      "settings.yaml",
      "firewall.yaml",
      "alerts.yaml",
      "notifications.yaml",
      "rbac.yaml",
    ] as const) {
      const lead = temporaryOverrideLead(doc);
      assert.match(lead, /temporary|live testing/i);
      assert.match(lead, new RegExp(`host/${doc.replace(".", "\\.")}`));
      assert.match(lead, /GitOps/);
      assert.match(lead, /wipe|replace/i);
      const guidance = temporaryOverrideGuidance(doc);
      assert.match(guidance, /GitOps repo/i);
      assert.match(guidance, /rbac\.write|RBAC/i);
      assert.match(guidance, /click-ops/i);
      const saved = temporaryOverrideSavedMessage(doc);
      assert.match(saved, /Temporary host override saved/i);
      assert.match(saved, /GitOps sync/);
      assert.match(saved, new RegExp(`host/${doc.replace(".", "\\.")}`));
    }
    assert.match(unsavedTemporaryOverrideMessage(), /Unsaved temporary override/);
  });

  it("exposes a disable_tips YAML snippet for durable tip dismissal", () => {
    assert.equal(disableTipsYamlSnippet(), "disable_tips: true\n");
  });

  it("warns that tip dismiss is temporary", async () => {
    const { temporaryTipsDismissMessage } = await import(
      "../../src/gitops/temporaryOverrideMessages.ts"
    );
    const msg = temporaryTipsDismissMessage("firewall.yaml");
    assert.match(msg, /temporary/i);
    assert.match(msg, /disable_tips: true/);
    assert.match(msg, /host\/firewall\.yaml/);
  });
});

describe("GitOps temporary-override wiring", () => {
  it("settings keep the page-level banner and override save copy", () => {
    const page = readFileSync(join(root, "src/settings/SettingsPage.tsx"), "utf8");
    const editor = readFileSync(
      join(root, "src/settings/useSettingsEditor.ts"),
      "utf8",
    );
    assert.match(page, /TemporaryOverrideBanner/);
    assert.match(page, /doc="settings\.yaml"/);
    assert.match(page, /temporary host overrides/i);
    assert.match(page, /unsavedTemporaryOverrideMessage/);
    assert.match(editor, /temporaryOverrideSavedMessage\("settings\.yaml"\)/);
  });

  it("firewall, alerts, and notifications share the banner + save warning", () => {
    const firewall = readFileSync(
      join(root, "src/firewall/FirewallPanel.tsx"),
      "utf8",
    );
    const alerts = readFileSync(
      join(root, "src/alerts/AlertsSettingsPage.tsx"),
      "utf8",
    );
    const notifications = readFileSync(
      join(root, "src/notifications/NotificationsSettingsPage.tsx"),
      "utf8",
    );
    assert.match(firewall, /TemporaryOverrideBanner/);
    assert.match(firewall, /DisableTipsCopyHint/);
    assert.match(firewall, /firewall\.yaml/);
    assert.match(alerts, /TemporaryOverrideBanner/);
    assert.match(alerts, /DisableTipsCopyHint/);
    assert.match(alerts, /alerts\.yaml/);
    assert.match(notifications, /TemporaryOverrideBanner/);
    assert.match(notifications, /notifications\.yaml/);
  });

  it("inspection firewall apply/remove warn temporary override", () => {
    const src = readFileSync(
      join(root, "src/service/httpRequests/InspectionFirewallActions.tsx"),
      "utf8",
    );
    assert.match(src, /temporaryOverrideSavedMessage\("firewall\.yaml"\)/);
    assert.doesNotMatch(src, /toast\.good\(/);
  });

  it("GitHub OAuth setup warns temporary override on settings.yaml", () => {
    const src = readFileSync(
      join(root, "src/deploy/oauth/OauthSetupPanel.tsx"),
      "utf8",
    );
    assert.match(src, /TemporaryOverrideBanner/);
    assert.match(src, /doc="settings\.yaml"/);
    assert.match(src, /temporaryOverrideSavedMessage\("settings\.yaml"\)/);
  });
});
