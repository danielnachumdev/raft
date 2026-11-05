/** Apply / validate section enablement against real RaftConfig semantics. */

import type { SettingsDocument, SettingsSection } from "./settingsApi";

export type EnabledMap = Record<string, boolean>;

export function enabledMapFromSections(sections: SettingsSection[]): EnabledMap {
  const out: EnabledMap = {};
  for (const section of sections) {
    out[section.key] = section.enabled;
  }
  return out;
}

export function applySectionEnabled(
  doc: SettingsDocument,
  key: string,
  enabled: boolean,
): SettingsDocument {
  switch (key) {
    case "healing":
      return { ...doc, healing: { ...doc.healing, enabled } };
    case "serviceLogs":
      return { ...doc, serviceLogs: { ...doc.serviceLogs, enabled } };
    case "notifications":
      return { ...doc, notifications: { ...doc.notifications, enabled } };
    case "alerts":
      return { ...doc, alerts: { ...doc.alerts, enabled } };
    case "dashboard":
      return { ...doc, dashboard: { ...doc.dashboard, enabled } };
    case "acme":
      return applyAcme(doc, enabled);
    case "github":
      return applyGithub(doc, enabled);
    default:
      return doc;
  }
}

function applyAcme(doc: SettingsDocument, enabled: boolean): SettingsDocument {
  if (enabled) return doc;
  return { ...doc, acme: { ...doc.acme, email: null } };
}

function applyGithub(doc: SettingsDocument, enabled: boolean): SettingsDocument {
  if (enabled) return doc;
  return {
    ...doc,
    github: {
      ...doc.github,
      clientId: null,
      clientSecret: null,
    },
  };
}

/** Client pre-check mirroring enablement rules before PUT (backend still validates). */
export function validateEnabledSections(
  doc: SettingsDocument,
  enabled: EnabledMap,
): string | null {
  if (enabled.acme && !doc.acme.email?.trim()) {
    return "ACME is enabled — set acme.email (e.g. ops@example.com) before Save.";
  }
  if (enabled.github && !doc.github.clientId?.trim()) {
    return "GitHub is enabled — set clientId before Save.";
  }
  if (enabled.dashboard && doc.dashboard.publicHost?.trim()) {
    const mode = doc.dashboard.auth.mode;
    if (mode === "none") {
      return "Dashboard publicHost requires auth.mode password, oauth, or external.";
    }
  }
  return null;
}
