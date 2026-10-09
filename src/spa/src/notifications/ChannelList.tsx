import type { NotificationChannel } from "./notificationsApi";
import {
  canSendTest,
  sendTestDisabledReason,
} from "./notificationsHelpers";
import type { NotificationStrategyInfo } from "./notificationsApi";
import "./ChannelList.css";

type Props = {
  channels: NotificationChannel[];
  strategies: NotificationStrategyInfo[];
  busyId: string | null;
  onEdit: (channel: NotificationChannel) => void;
  onToggle: (channel: NotificationChannel) => void;
  onDelete: (channel: NotificationChannel) => void;
};

/** Channel rows with enable/disable, edit, delete; Send test when available. */
export function ChannelList(props: Props) {
  if (props.channels.length === 0) {
    return (
      <p className="muted" id="channels-empty">
        No notification channels configured.
      </p>
    );
  }

  return (
    <ul className="channel-list" id="channel-list">
      {props.channels.map((channel) => (
        <ChannelRow
          key={channel.id}
          channel={channel}
          strategies={props.strategies}
          busy={props.busyId === channel.id}
          onEdit={() => props.onEdit(channel)}
          onToggle={() => props.onToggle(channel)}
          onDelete={() => props.onDelete(channel)}
        />
      ))}
    </ul>
  );
}

function ChannelRow(props: {
  channel: NotificationChannel;
  strategies: NotificationStrategyInfo[];
  busy: boolean;
  onEdit: () => void;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const { channel } = props;
  const sendOk = canSendTest(props.strategies, channel.type);
  const sendTitle = sendOk
    ? "Send a test notification"
    : sendTestDisabledReason(props.strategies, channel.type);

  return (
    <li className="channel-row" data-channel-id={channel.id}>
      <div className="channel-row-main">
        <strong className="channel-id">{channel.id}</strong>
        <span className="muted channel-meta">
          type <code>{channel.type}</code>
          {" · "}
          {channel.enabled ? "enabled" : "disabled"}
        </span>
        <SettingsPreview settings={channel.settings} />
      </div>
      <div className="channel-row-actions">
        <button
          type="button"
          className="action-btn"
          disabled={props.busy}
          onClick={props.onToggle}
          id={`channel-toggle-${channel.id}`}
        >
          {channel.enabled ? "Disable" : "Enable"}
        </button>
        <button
          type="button"
          className="action-btn"
          disabled={props.busy}
          onClick={props.onEdit}
          id={`channel-edit-${channel.id}`}
        >
          Edit
        </button>
        <button
          type="button"
          className="action-btn"
          disabled={!sendOk || props.busy}
          title={sendTitle}
          id={`channel-test-${channel.id}`}
        >
          Send test
        </button>
        <button
          type="button"
          className="action-btn action-btn-danger"
          disabled={props.busy}
          onClick={props.onDelete}
          id={`channel-delete-${channel.id}`}
        >
          Delete
        </button>
      </div>
    </li>
  );
}

function SettingsPreview(props: { settings: Record<string, unknown> }) {
  const keys = Object.keys(props.settings);
  if (keys.length === 0) {
    return <span className="muted channel-settings-preview">settings {"{}"}</span>;
  }
  const summary = keys
    .slice(0, 4)
    .map((key) => `${key}=${previewValue(props.settings[key])}`)
    .join(", ");
  const more = keys.length > 4 ? `, +${keys.length - 4}` : "";
  return (
    <span className="muted channel-settings-preview">
      {summary}
      {more}
    </span>
  );
}

function previewValue(value: unknown): string {
  if (value === null || value === undefined) return String(value);
  if (typeof value === "string") {
    return value.length > 40 ? `${value.slice(0, 37)}…` : value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "…";
}
