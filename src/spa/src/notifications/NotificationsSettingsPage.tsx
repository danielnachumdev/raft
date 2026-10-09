import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ConfirmPopup } from "../chrome/ConfirmPopup";
import { toast } from "../chrome/toast";
import { ChannelFormModal, type ChannelFormSubmit } from "./ChannelFormModal";
import { ChannelList } from "./ChannelList";
import {
  createNotificationChannel,
  deleteNotificationChannel,
  fetchNotificationChannels,
  fetchNotificationStrategies,
  updateNotificationChannel,
  type NotificationChannel,
  type NotificationStrategyInfo,
} from "./notificationsApi";
import { isEmptyStrategyCatalog } from "./notificationsHelpers";
import "../deploy/DeployPage.css";
import "./NotificationsSettingsPage.css";

/** Settings page: list / add / edit / enable notification channels. */
export function NotificationsSettingsPage() {
  const [strategies, setStrategies] = useState<NotificationStrategyInfo[]>([]);
  const [channels, setChannels] = useState<NotificationChannel[]>([]);
  const [globalEnabled, setGlobalEnabled] = useState(true);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [editing, setEditing] = useState<NotificationChannel | null>(null);
  const [formBusy, setFormBusy] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<NotificationChannel | null>(
    null,
  );

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const [strat, list] = await Promise.all([
        fetchNotificationStrategies(),
        fetchNotificationChannels(),
      ]);
      setStrategies(strat.strategies);
      setChannels(list.channels);
      setGlobalEnabled(list.enabled);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load notifications");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const catalogEmpty = isEmptyStrategyCatalog(strategies);

  return (
    <div className="page notifications-page">
      <header className="header">
        <div>
          <p className="brand">raft</p>
          <h1>Notifications</h1>
          <p className="muted header-updating">
            Manage notification channels for this host. Secrets stay redacted.
          </p>
        </div>
        <Link className="refresh" to="/" id="notifications-back">
          Stack status
        </Link>
      </header>

      {busy ? (
        <div className="loading" role="status" aria-busy="true">
          <span className="spinner" aria-hidden="true" />
          <p>Loading notifications…</p>
        </div>
      ) : null}

      {error ? (
        <p className="error" role="alert" id="notifications-error">
          {error}
        </p>
      ) : null}

      {!busy && !error ? (
        <>
          {catalogEmpty ? (
            <section
              className="deploy-panel notifications-empty-catalog"
              id="notifications-empty-catalog"
            >
              <h2>No strategies registered</h2>
              <p className="muted">
                The notification strategy catalog is empty. Install or register a
                delivery strategy before adding channels. Existing channels (if
                any) still appear below; types are not invented in this UI.
              </p>
            </section>
          ) : null}

          <section className="deploy-panel" id="notifications-channels">
            <div className="notifications-panel-head">
              <div>
                <h2>Channels</h2>
                <p className="muted notifications-global">
                  Global notifications: {globalEnabled ? "on" : "off"}{" "}
                  <span className="muted">(settings.yaml)</span>
                </p>
              </div>
              <button
                type="button"
                className="refresh"
                id="notifications-add"
                disabled={catalogEmpty}
                title={
                  catalogEmpty
                    ? "Register a strategy before adding a channel"
                    : "Add channel"
                }
                onClick={openCreate}
              >
                Add channel
              </button>
            </div>
            <ChannelList
              channels={channels}
              strategies={strategies}
              busyId={busyId}
              onEdit={openEdit}
              onToggle={(ch) => void toggleEnabled(ch)}
              onDelete={setPendingDelete}
            />
          </section>
        </>
      ) : null}

      <ChannelFormModal
        open={formOpen}
        mode={formMode}
        strategies={strategies}
        channel={editing}
        busy={formBusy}
        onClose={() => setFormOpen(false)}
        onSubmit={(values) => void saveChannel(values)}
      />

      <ConfirmPopup
        open={pendingDelete !== null}
        title="Delete channel"
        message={
          pendingDelete
            ? `Delete notification channel “${pendingDelete.id}”? This writes settings.yaml.`
            : ""
        }
        confirmLabel="Delete"
        danger
        onConfirm={() => void confirmDelete()}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );

  function openCreate() {
    setFormMode("create");
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(channel: NotificationChannel) {
    setFormMode("edit");
    setEditing(channel);
    setFormOpen(true);
  }

  async function saveChannel(values: ChannelFormSubmit) {
    setFormBusy(true);
    try {
      if (formMode === "create") {
        await createNotificationChannel(values);
        toast.good(`Channel ${values.id} created`);
      } else {
        await updateNotificationChannel(values.id, {
          type: values.type,
          enabled: values.enabled,
          settings: values.settings,
        });
        toast.good(`Channel ${values.id} updated`);
      }
      setFormOpen(false);
      await load();
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Save failed");
    } finally {
      setFormBusy(false);
    }
  }

  async function toggleEnabled(channel: NotificationChannel) {
    setBusyId(channel.id);
    try {
      await updateNotificationChannel(channel.id, {
        enabled: !channel.enabled,
      });
      toast.good(
        `Channel ${channel.id} ${channel.enabled ? "disabled" : "enabled"}`,
      );
      await load();
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusyId(null);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    const id = pendingDelete.id;
    setBusyId(id);
    try {
      await deleteNotificationChannel(id);
      toast.good(`Channel ${id} deleted`);
      setPendingDelete(null);
      await load();
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Delete failed");
      throw err;
    } finally {
      setBusyId(null);
    }
  }
}
