import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "../chrome/toast";
import {
  dismissInboxItem,
  markInboxItemRead,
  markInboxItemUnread,
  type InboxItem,
  type InboxPayload,
} from "./inboxApi";

type Props = {
  item: InboxItem;
  onChange: (next: InboxPayload) => void;
};

/** One inbox row with open / read / dismiss controls. */
export function InboxRow(props: Props) {
  const { item } = props;
  const [pending, setPending] = useState(false);

  async function run(action: () => Promise<InboxPayload>, ok: string) {
    setPending(true);
    try {
      props.onChange(await action());
      toast.good(ok);
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Action failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <li
      className={
        item.unread ? "item-row inbox-row is-unread" : "item-row inbox-row"
      }
      data-inbox-id={item.id}
      data-inbox-source={item.source}
    >
      <div className="item-row-main">
        <div className="item-row-title">
          {item.unread ? (
            <span className="inbox-unread-dot" aria-hidden="true" />
          ) : null}
          <strong>{item.title}</strong>
          <span className="inbox-source-tag">{sourceLabel(item.source)}</span>
        </div>
        <p className="item-row-meta">{item.summary}</p>
      </div>
      <RowActions item={item} pending={pending} run={run} onChange={props.onChange} />
    </li>
  );
}

function RowActions(props: {
  item: InboxItem;
  pending: boolean;
  run: (action: () => Promise<InboxPayload>, ok: string) => Promise<void>;
  onChange: (next: InboxPayload) => void;
}) {
  const { item, pending, run, onChange } = props;
  const sid = cssId(item.id);
  return (
    <div className="btn-group item-row-actions">
      {item.href ? (
        <Link
          className="btn btn-sm"
          to={item.href}
          id={`inbox-open-${sid}`}
          onClick={() => {
            if (item.unread) {
              void markInboxItemRead(item.id).then(onChange).catch(() => undefined);
            }
          }}
        >
          Open
        </Link>
      ) : null}
      {item.unread ? (
        <button
          type="button"
          className="btn btn-sm"
          disabled={pending}
          id={`inbox-read-${sid}`}
          onClick={() => void run(() => markInboxItemRead(item.id), "Marked read")}
        >
          Mark read
        </button>
      ) : (
        <button
          type="button"
          className="btn btn-sm"
          disabled={pending}
          id={`inbox-unread-${sid}`}
          onClick={() =>
            void run(() => markInboxItemUnread(item.id), "Marked unread")
          }
        >
          Mark unread
        </button>
      )}
      {item.dismissible ? (
        <button
          type="button"
          className="btn btn-sm"
          disabled={pending}
          id={`inbox-dismiss-${sid}`}
          onClick={() => void run(() => dismissInboxItem(item.id), "Dismissed")}
        >
          Dismiss
        </button>
      ) : null}
    </div>
  );
}

function sourceLabel(source: string): string {
  if (source === "firewall-recommendation") return "Firewall";
  if (source === "alerts-recommendation") return "Alerts";
  return source;
}

function cssId(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]+/g, "-");
}
