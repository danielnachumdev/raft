import { Link } from "react-router-dom";
import { SectionCard } from "../SectionCard";
import type { SettingsDocument } from "../settingsApi";

export function NotificationsSection(props: {
  value: SettingsDocument["notifications"];
  onChange: (next: SettingsDocument["notifications"]) => void;
}) {
  const v = props.value;
  return (
    <SectionCard
      id="settings-notifications"
      title="Notifications"
      hint={
        <>
          Global switch for outbound channels. Manage channel CRUD on{" "}
          <Link to="/settings/notifications">Settings → Notifications</Link>.
        </>
      }
    >
      <label className="check">
        <input
          type="checkbox"
          checked={v.enabled}
          onChange={(e) =>
            props.onChange({ ...v, enabled: e.target.checked })
          }
        />
        Global notifications enabled
      </label>
      <p className="muted" id="settings-notifications-count">
        {v.channels.length} channel{v.channels.length === 1 ? "" : "s"} in
        settings.yaml (secrets stay redacted here).
      </p>
    </SectionCard>
  );
}
