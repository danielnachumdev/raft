import type { NotificationChannel } from "./notificationsApi";
import {
  canSendTest,
  sendTestDisabledReason,
} from "./notificationsHelpers";
import type { NotificationStrategyInfo } from "./notificationsApi";
import { EmptyState } from "../chrome/StateViews";
import "./ChannelList.css";

type Props = {
  channels: NotificationChannel[];
  strategies: NotificationStrategyInfo[];
  busyId: string | null;
  onEdit: (channel: NotificationChannel) => void;
  onToggle: (channel: NotificationChannel) => void;
  onDelete: (channel: NotificationChannel) => void;
  onSendTest: (channel: NotificationChannel) => void;
};

/** Channel rows with enable/disable, edit, delete; Send test when available. */
export function ChannelList(props: Props) {
  if (props.channels.length === 0) {
    return (
      <EmptyState id="channels-empty" title="No notification channels configured.">
        Use <em>Add channel</em> so raft alerts for this host reach you.
      </EmptyState>
    );
  }

  return (
    <ul className="item-list" id="channel-list">
      {props.channels.map((channel) => (
        <ChannelRow
          key={channel.id}
          channel={channel}
          strategies={props.strategies}
          busy={props.busyId === channel.id}
          onEdit={() => props.onEdit(channel)}
          onToggle={() => props.onToggle(channel)}
          onDelete={() => props.onDelete(channel)}
          onSendTest={() => props.onSendTest(channel)}
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
  onSendTest: () => void;
}) {
  const { channel } = props;
  const sendOk = canSendTest(props.strategies, channel.type);
  const sendTitle = sendOk
    ? "Send a test notification"
    : sendTestDisabledReason(props.strategies, channel.type);

  return (
    <li
      className={channel.enabled ? "item-row" : "item-row is-disabled"}
      data-channel-id={channel.id}
    >
      <div className="item-row-main">
        <div className="item-row-title">
          <strong className="channel-id">{channel.id}</strong>
          <span className={channel.enabled ? "chip chip-ok" : "chip"}>
            {channel.enabled ? "Enabled" : "Disabled"}
          </span>
          <span className="chip channel-type" title="Delivery strategy">
            {channel.type}
          </span>
        </div>
        <SettingsPreview settings={channel.settings} />
      </div>
      <div className="btn-group item-row-actions">
        <button
          type="button"
          className="btn btn-sm"
          disabled={props.busy}
          onClick={props.onToggle}
          id={`channel-toggle-${channel.id}`}
        >
          {channel.enabled ? "Disable" : "Enable"}
        </button>
        <button
          type="button"
          className="btn btn-sm"
          disabled={props.busy}
          onClick={props.onEdit}
          id={`channel-edit-${channel.id}`}
        >
          Edit
        </button>
        <button
          type="button"
          className="btn btn-sm"
          disabled={!sendOk || props.busy}
          title={sendTitle}
          id={`channel-test-${channel.id}`}
          onClick={props.onSendTest}
        >
          Send test
        </button>
        <button
          type="button"
          className="btn btn-sm btn-danger"
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
    return <p className="item-row-meta">No settings</p>;
  }
  const summary = keys
    .slice(0, 4)
    .map((key) => `${key}=${previewValue(props.settings[key])}`)
    .join(", ");
  const more = keys.length > 4 ? `, +${keys.length - 4}` : "";
  return (
    <p className="item-row-meta">
      <code className="channel-settings-preview">
        {summary}
        {more}
      </code>
    </p>
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
