import { Link } from "react-router-dom";
import { SectionCard } from "../SectionCard";
import type { SettingsDocument, SettingsSection } from "../settingsApi";

export function NotificationsSection(props: {
  value: SettingsDocument["notifications"];
  meta?: SettingsSection;
  enabled: boolean;
  onEnabledChange: (enabled: boolean) => void;
  onChange: (next: SettingsDocument["notifications"]) => void;
}) {
  const v = props.value;
  return (
    <SectionCard
      id="settings-notifications"
      title="Notifications"
      kind={props.meta?.kind ?? "flag"}
      enabled={props.enabled}
      source={props.meta?.source}
      onEnabledChange={props.onEnabledChange}
      hint={
        <>
          Global switch for outbound channels. Manage channel CRUD on{" "}
          <Link to="/settings/notifications">Settings → Notifications</Link>.
        </>
      }
    >
      <p className="muted" id="settings-notifications-count">
        {v.channels.length} channel{v.channels.length === 1 ? "" : "s"} in
        settings.yaml (secrets stay redacted here).
      </p>
    </SectionCard>
  );
}
