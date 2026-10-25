import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../chrome/StateViews";
import { toast } from "../chrome/toast";
import { PageHeader } from "../shell/PageHeader";
import {
  fetchInbox,
  markAllInboxRead,
  type InboxItem,
  type InboxPayload,
} from "./inboxApi";
import { InboxRow } from "./InboxRow";
import "./InboxPage.css";

/** Manage in-app operator notices (recommendations); not outbound channels. */
export function InboxPage() {
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<InboxPayload | null>(null);

  const load = useCallback(async (opts?: { quiet?: boolean }) => {
    if (!opts?.quiet) setBusy(true);
    try {
      setPayload(await fetchInbox());
      setError(null);
    } catch (err) {
      if (!opts?.quiet) setPayload(null);
      setError(err instanceof Error ? err.message : "Failed to load inbox");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onMarkAllRead() {
    try {
      setPayload(await markAllInboxRead());
      toast.good("Marked all as read");
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Mark all read failed");
    }
  }

  return (
    <div className="inbox-page">
      <PageHeader
        title="Inbox"
        subtitle="Operator notices from setup recommendations and similar attention items. Separate from Settings → Notifications (outbound email/Slack channels)."
        actions={
          <div className="btn-group">
            <button
              type="button"
              className={busy ? "btn is-loading" : "btn"}
              id="inbox-refresh"
              onClick={() => void load()}
              disabled={busy}
            >
              Refresh
            </button>
            <button
              type="button"
              className="btn"
              id="inbox-mark-all-read"
              onClick={() => void onMarkAllRead()}
              disabled={busy || !(payload?.unreadCount)}
            >
              Mark all read
            </button>
          </div>
        }
      />
      {busy && !payload ? <LoadingState label="Loading inbox…" /> : null}
      {error && !payload ? (
        <ErrorState
          message={error}
          id="inbox-page-error"
          onRetry={() => void load()}
        />
      ) : null}
      {payload ? <InboxList items={payload.items} onChange={setPayload} /> : null}
    </div>
  );
}

function InboxList(props: {
  items: InboxItem[];
  onChange: (next: InboxPayload) => void;
}) {
  if (props.items.length === 0) {
    return (
      <EmptyState
        id="inbox-empty"
        title="Inbox is clear"
        action={
          <Link className="btn btn-sm" to="/settings/edge-access">
            Open Firewall
          </Link>
        }
      >
        No pending recommendations need attention. Outbound channels stay under
        Settings → Notifications.
      </EmptyState>
    );
  }

  return (
    <section className="panel" id="inbox-panel" aria-label="Inbox items">
      <ul className="item-list inbox-list">
        {props.items.map((item) => (
          <InboxRow key={item.id} item={item} onChange={props.onChange} />
        ))}
      </ul>
    </section>
  );
}
