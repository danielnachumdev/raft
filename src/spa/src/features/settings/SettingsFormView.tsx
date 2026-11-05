import type { EnabledMap } from "./sectionEnablement";
import type { SettingsDocument, SettingsSection } from "./settingsApi";
import {
  AcmeSection,
  AlertsSection,
  DashboardSection,
  EdgeSection,
  GithubSection,
  HealingSection,
  LoggingSection,
  MetricsSection,
  NotificationsSection,
  ServiceLogsSection,
  StorageSection,
} from "./sections";

/** Form mode: one card per RaftConfig section + Storage (not yaml). */
export function SettingsFormView(props: {
  draft: SettingsDocument;
  sections: SettingsSection[];
  enabled: EnabledMap;
  onPatch: <K extends keyof SettingsDocument>(
    key: K,
    value: SettingsDocument[K],
  ) => void;
  onEnabledChange: (key: string, enabled: boolean) => void;
}) {
  const meta = (key: string) =>
    props.sections.find((section) => section.key === key);
  const on = (key: string) => props.enabled[key] ?? true;
  const toggle = (key: string) => (enabled: boolean) =>
    props.onEnabledChange(key, enabled);
  const d = props.draft;

  return (
    <>
      <LoggingSection
        value={d.logging}
        meta={meta("logging")}
        onChange={(logging) => props.onPatch("logging", logging)}
      />
      <EdgeSection
        value={d.edge}
        meta={meta("edge")}
        onChange={(edge) => props.onPatch("edge", edge)}
      />
      <HealingSection
        value={d.healing}
        meta={meta("healing")}
        enabled={on("healing")}
        onEnabledChange={toggle("healing")}
        onChange={(healing) => props.onPatch("healing", healing)}
      />
      <MetricsSection
        value={d.metrics}
        meta={meta("metrics")}
        onChange={(metrics) => props.onPatch("metrics", metrics)}
      />
      <ServiceLogsSection
        value={d.serviceLogs}
        meta={meta("serviceLogs")}
        enabled={on("serviceLogs")}
        onEnabledChange={toggle("serviceLogs")}
        onChange={(serviceLogs) => props.onPatch("serviceLogs", serviceLogs)}
      />
      <AcmeSection
        value={d.acme}
        meta={meta("acme")}
        enabled={on("acme")}
        onEnabledChange={toggle("acme")}
        onChange={(acme) => props.onPatch("acme", acme)}
      />
      <GithubSection
        value={d.github}
        meta={meta("github")}
        enabled={on("github")}
        onEnabledChange={toggle("github")}
        onChange={(github) => props.onPatch("github", github)}
      />
      <NotificationsSection
        value={d.notifications}
        meta={meta("notifications")}
        enabled={on("notifications")}
        onEnabledChange={toggle("notifications")}
        onChange={(notifications) =>
          props.onPatch("notifications", notifications)
        }
      />
      <AlertsSection
        value={d.alerts}
        meta={meta("alerts")}
        enabled={on("alerts")}
        onEnabledChange={toggle("alerts")}
        onChange={(alerts) => props.onPatch("alerts", alerts)}
      />
      <DashboardSection
        value={d.dashboard}
        meta={meta("dashboard")}
        enabled={on("dashboard")}
        onEnabledChange={toggle("dashboard")}
        onChange={(dashboard) => props.onPatch("dashboard", dashboard)}
      />
      <StorageSection />
    </>
  );
}
