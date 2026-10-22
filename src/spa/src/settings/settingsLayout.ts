/** Section index + unsaved-change detection for the Settings page. */

import type { EnabledMap } from "./sectionEnablement";
import type { SettingsDocument } from "./settingsApi";

export type SettingsNavItem = {
  /** DOM id of the ``SectionCard`` (anchor target). */
  id: string;
  label: string;
  /** ``EnabledMap`` key when the section has an enable toggle. */
  key?: string;
};

export type SettingsNavGroup = { label: string; items: SettingsNavItem[] };

export const SETTINGS_NAV_GROUPS: SettingsNavGroup[] = [
  {
    label: "General",
    items: [
      { id: "settings-appearance", label: "Appearance" },
      { id: "settings-updates", label: "Updates" },
      { id: "settings-about", label: "About" },
    ],
  },
  {
    label: "Platform",
    items: [
      { id: "settings-logging", label: "Logging" },
      { id: "settings-edge", label: "Edge" },
      { id: "settings-healing", label: "Healing", key: "healing" },
      { id: "settings-metrics", label: "Metrics" },
      { id: "settings-service-logs", label: "Service logs", key: "serviceLogs" },
      { id: "settings-acme", label: "ACME", key: "acme" },
    ],
  },
  {
    label: "Integrations",
    items: [
      { id: "settings-github", label: "GitHub", key: "github" },
      { id: "settings-notifications", label: "Notifications", key: "notifications" },
      { id: "settings-alerts", label: "Alerts", key: "alerts" },
      { id: "settings-dashboard", label: "Dashboard", key: "dashboard" },
    ],
  },
  {
    label: "Maintenance",
    items: [{ id: "settings-storage", label: "Storage" }],
  },
];

/** Dedicated pages that own the CRUD behind a settings toggle. */
export const SETTINGS_RELATED_PAGES = [
  { to: "/settings/alerts", label: "Alert rules" },
  { to: "/settings/notifications", label: "Notification channels" },
  { to: "/settings/edge-access", label: "Firewall rules" },
];

/** Every section anchor id, in nav order. */
export function settingsNavIds(): string[] {
  return SETTINGS_NAV_GROUPS.flatMap((group) => group.items.map((i) => i.id));
}

/** True when a toggle-able section is currently switched off. */
export function sectionOff(item: SettingsNavItem, enabled: EnabledMap): boolean {
  return item.key ? enabled[item.key] === false : false;
}

export type DirtyInput = {
  mode: "form" | "yaml";
  draft: SettingsDocument | null;
  /** ``JSON.stringify`` of the last loaded / saved document. */
  savedJson: string;
  yamlText: string;
  /** YAML text when the editor entered YAML mode (or after save). */
  yamlBaseline: string;
};

/** Form edits, or YAML edits since entering YAML mode, are unsaved. */
export function settingsDirty(input: DirtyInput): boolean {
  if (!input.draft) return false;
  const formDirty = JSON.stringify(input.draft) !== input.savedJson;
  if (input.mode === "form") return formDirty;
  return formDirty || input.yamlText !== input.yamlBaseline;
}
