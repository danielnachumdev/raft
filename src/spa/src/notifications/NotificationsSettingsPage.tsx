import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ConfirmPopup } from "../chrome/ConfirmPopup";
import { ItemPanelSkeleton, showSkeleton } from "../chrome/skeleton";
import { ErrorState } from "../chrome/StateViews";
import { PageHeader } from "../shell/PageHeader";
import { toast } from "../chrome/toast";
import {
  TemporaryOverrideBanner,
  temporaryOverrideSavedMessage,
} from "../gitops";
import { ChannelFormModal, type ChannelFormSubmit } from "./ChannelFormModal";
import { ChannelList } from "./ChannelList";
import {
  createNotificationChannel,
  deleteNotificationChannel,
  fetchNotificationChannels,
  fetchNotificationStrategies,
  sendNotificationTest,
  updateNotificationChannel,
  type NotificationChannel,
  type NotificationStrategyInfo,
} from "./notificationsApi";
import { isEmptyStrategyCatalog } from "./notificationsHelpers";
import "./NotificationsSettingsPage.css";
import { userFacingError } from "../shared/userFacingError.ts";

/** Settings page: list / add / edit / enable notification channels. */
export function NotificationsSettingsPage() {
  const [strategies, setStrategies] = useState<NotificationStrategyInfo[]>([]);
  const [channels, setChannels] = useState<NotificationChannel[]>([]);
  const [globalEnabled, setGlobalEnabled] = useState(true);
  const [busy, setBusy] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [editing, setEditing] = useState<NotificationChannel | null>(null);
  const [formBusy, setFormBusy] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<NotificationChannel | null>(
    null,
  );

  async function load(opts?: { quiet?: boolean }) {
    const quiet = opts?.quiet === true && loaded;
    setError(null);
    if (!quiet) setBusy(true);
    try {
      const [strat, list] = await Promise.all([
        fetchNotificationStrategies(),
        fetchNotificationChannels(),
      ]);
      setStrategies(strat.strategies);
      setChannels(list.channels);
      setGlobalEnabled(list.enabled);
      setLoaded(true);
    } catch (err) {
      setError(userFacingError(err, "Failed to load notifications"));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const catalogEmpty = isEmptyStrategyCatalog(strategies);

  return (
    <div className="notifications-page">
      <PageHeader
        title="Notifications"
        subtitle="Where alerts for this host are sent. Secrets stay redacted."
        meta={
          !busy && !error ? (
            <Link
              className={globalEnabled ? "chip chip-ok" : "chip chip-warn"}
              id="notifications-global"
              title="Global notifications switch in Settings"
              to="/settings#settings-notifications"
            >
              Global notifications {globalEnabled ? "on" : "off"}
            </Link>
          ) : undefined
        }
        actions={
          <button
            type="button"
            className="btn btn-primary"
            id="notifications-add"
            disabled={busy || catalogEmpty}
            title={
              catalogEmpty
                ? "Register a strategy before adding a channel"
                : "Add channel"
            }
            onClick={openCreate}
          >
            Add channel
          </button>
        }
      />

      {showSkeleton(busy, loaded) ? (
        <ItemPanelSkeleton
          label="Loading notifications…"
          id="notifications-loading"
          titleWidth="4.5rem"
          panelId="notifications-channels-skeleton"
        />
      ) : null}

      {error ? (
        <ErrorState
          message={error}
          id="notifications-error"
          onRetry={() => void load({ quiet: loaded })}
        />
      ) : null}

      {loaded && !error ? (
        <>
          <TemporaryOverrideBanner
            doc="notifications.yaml"
            id="notifications-temp-override"
          />
          {catalogEmpty ? (
            <section
              className="callout callout-warn notifications-empty-catalog"
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

          <section className="panel" id="notifications-channels">
            <div className="panel-head">
              <h2>
                Channels
                {channels.length ? (
                  <span className="panel-count">{channels.length}</span>
                ) : null}
              </h2>
            </div>
            <ChannelList
              channels={channels}
              strategies={strategies}
              busyId={busyId}
              onEdit={openEdit}
              onToggle={(ch) => void toggleEnabled(ch)}
              onDelete={setPendingDelete}
              onSendTest={(ch) => void sendTest(ch)}
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
            ? `Delete notification channel “${pendingDelete.id}”? This updates host settings.`
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
      } else {
        await updateNotificationChannel(values.id, {
          type: values.type,
          enabled: values.enabled,
          settings: values.settings,
        });
      }
      toast.warning(temporaryOverrideSavedMessage("notifications.yaml"));
      setFormOpen(false);
      await load({ quiet: true });
    } catch (err) {
      toast.bad(userFacingError(err, "Save failed"));
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
      toast.warning(temporaryOverrideSavedMessage("notifications.yaml"));
      await load({ quiet: true });
    } catch (err) {
      toast.bad(userFacingError(err, "Update failed"));
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
      toast.warning(temporaryOverrideSavedMessage("notifications.yaml"));
      setPendingDelete(null);
      await load({ quiet: true });
    } catch (err) {
      toast.bad(userFacingError(err, "Delete failed"));
      throw err;
    } finally {
      setBusyId(null);
    }
  }

  async function sendTest(channel: NotificationChannel) {
    setBusyId(channel.id);
    try {
      const result = await sendNotificationTest(channel.id);
      if (result.ok) toast.good(result.message);
      else toast.bad(result.message);
    } catch (err) {
      toast.bad(userFacingError(err, "Test failed"));
    } finally {
      setBusyId(null);
    }
  }
}
