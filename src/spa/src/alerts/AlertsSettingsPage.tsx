import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { Link } from "react-router-dom";
import { ConfirmPopup } from "../chrome/ConfirmPopup";
import { LiveIndicator } from "../chrome/LiveIndicator";
import { toast } from "../chrome/toast";
import { fetchNotificationChannels } from "../notifications/notificationsApi";
import type { NotificationChannel } from "../notifications/notificationsApi";
import { PageHeader } from "../shell/PageHeader";
import { bindStatusPolling } from "../shell/statusPolling";
import { AlertCallouts, RulesEmpty } from "./AlertCallouts";
import { AlertFiringPanel } from "./AlertFiringPanel";
import { AlertImportModal } from "./AlertImportModal";
import { AlertRuleFormModal, type AlertFormMode } from "./AlertRuleFormModal";
import { AlertRuleList } from "./AlertRuleList";
import {
  catalogProxy,
  createAlertRule,
  fetchAlertCatalog,
  fetchAlertRules,
  fetchAlertStatus,
  replaceAlertRule,
  type AlertStatusPayload,
} from "./alertsApi";
import { emptyRuleDraft, type AlertCatalogPayload, type AlertRule } from "./alertsHelpers";
import { applyImport, downloadAlertRules, readImportFile, useAlertRuleActions } from "./useAlertRuleActions";
import "./AlertsSettingsPage.css";

type PendingImport = { fileName: string; doc: { version: number; rules: AlertRule[] } };

export function AlertsSettingsPage() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [catalog, setCatalog] = useState<AlertCatalogPayload | null>(null);
  const [channels, setChannels] = useState<NotificationChannel[]>([]);
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [status, setStatus] = useState<AlertStatusPayload | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [form, setForm] = useState<{ mode: AlertFormMode; rule: AlertRule } | null>(null);
  const [formBusy, setFormBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<AlertRule | null>(null);
  const [pendingImport, setPendingImport] = useState<PendingImport | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const actions = useAlertRuleActions(load);

  async function load() {
    setError(null);
    try {
      await catalogProxy.refresh();
      const [r, c, ch, s] = await Promise.all([
        fetchAlertRules(),
        fetchAlertCatalog(),
        fetchNotificationChannels(),
        fetchAlertStatus(),
      ]);
      setRules(r.rules);
      setCatalog(c);
      setChannels(ch.channels);
      setNotificationsEnabled(ch.enabled);
      setStatus(s);
      setNow(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load alerts");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(
    () =>
      bindStatusPolling(
        () =>
          void fetchAlertStatus()
            .then((payload) => {
              setStatus(payload);
              setNow(Date.now());
            })
            .catch(() => undefined),
        setLive,
        10_000,
      ),
    [],
  );

  const enabledChannels = channels.filter((c) => c.enabled);
  const interval = status?.intervalSeconds ?? 60;

  return (
    <div className="alerts-page" id="alerts-page">
      <PageHeader
        title="Alerts"
        subtitle="Rules that watch metrics and control-plane signals and send through your notification channels."
        meta={
          <>
            <span className={status?.enabled === false ? "chip chip-warn" : "chip"}>
              {status?.enabled === false ? "Alerts disabled in settings.yaml" : `Evaluating every ${interval}s`}
            </span>
            {!notificationsEnabled ? (
              <Link className="chip chip-warn" to="/settings/notifications">
                Notifications off
              </Link>
            ) : null}
            <LiveIndicator isLive={live} />
          </>
        }
        actions={
          <>
            <button type="button" className="btn" id="alerts-import" onClick={() => fileInput.current?.click()}>
              Import
            </button>
            <input ref={fileInput} type="file" accept="application/json,.json" hidden onChange={onFilePicked} />
            <button type="button" className="btn" id="alerts-export" onClick={() => void downloadAlertRules()}>
              Export
            </button>
            <button
              type="button"
              className="btn btn-primary"
              id="alerts-add"
              disabled={busy || !catalog}
              onClick={() => catalog && openForm("create", emptyRuleDraft(catalog))}
            >
              Add rule
            </button>
          </>
        }
      />

      {busy ? (
        <div className="loading" role="status">
          <span className="spinner" aria-hidden="true" />
          <p>Loading alerts…</p>
        </div>
      ) : null}
      {error ? (
        <div className="callout callout-bad alerts-error" id="alerts-error" role="alert">
          <span>{error}</span>
          <button type="button" className="btn btn-sm" onClick={() => void load()}>
            Retry
          </button>
        </div>
      ) : null}
      <AlertCallouts status={status} hasChannels={enabledChannels.length > 0} />

      {!busy ? (
        <>
          <AlertFiringPanel status={status} interval={interval} now={now} />
          <section className="panel" id="alerts-rules">
            <div className="panel-head">
              <h2>
                Rules<span className="panel-count">{rules.length}</span>
              </h2>
            </div>
            {rules.length ? (
              <AlertRuleList
                rules={rules}
                status={status}
                catalog={catalog}
                channels={channels}
                busyId={actions.busyId}
                canTest={enabledChannels.length > 0}
                onEdit={(rule) => openForm("edit", rule)}
                onToggle={(rule) => void actions.toggle(rule)}
                onDryRun={(rule) => void actions.dryRun(rule)}
                onTest={(rule) => void actions.sendTest(rule)}
                onDelete={setDeleting}
              />
            ) : (
              <RulesEmpty />
            )}
          </section>
        </>
      ) : null}

      {form ? (
        <AlertRuleFormModal
          key={`${form.mode}-${form.rule.id}`}
          mode={form.mode}
          initial={form.rule}
          catalog={catalog}
          channels={channels}
          busy={formBusy}
          error={formError}
          onClose={() => setForm(null)}
          onSubmit={saveRule}
        />
      ) : null}
      <ConfirmPopup
        open={deleting !== null}
        title="Delete alert rule?"
        message={`Deletes ${deleting?.id ?? ""} and its evaluation state. Export first if you may want it back.`}
        confirmLabel="Delete"
        danger
        onCancel={() => setDeleting(null)}
        onConfirm={async () => {
          if (deleting) await actions.remove(deleting);
          setDeleting(null);
        }}
      />
      {pendingImport ? (
        <AlertImportModal
          fileName={pendingImport.fileName}
          rules={pendingImport.doc.rules}
          existing={rules.length}
          onCancel={() => setPendingImport(null)}
          onImport={runImport}
        />
      ) : null}
    </div>
  );

  function openForm(mode: AlertFormMode, rule: AlertRule) {
    setFormError(null);
    setForm({ mode, rule });
  }

  async function saveRule(rule: AlertRule) {
    if (!form) return;
    setFormBusy(true);
    setFormError(null);
    try {
      if (form.mode === "create") await createAlertRule(rule);
      else await replaceAlertRule(rule.id, rule);
      toast.good(form.mode === "create" ? `Created ${rule.id}` : `Saved ${rule.id}`);
      setForm(null);
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setFormBusy(false);
    }
  }

  function onFilePicked(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    readImportFile(file)
      .then((doc) => setPendingImport({ fileName: file.name, doc }))
      .catch((err: unknown) => toast.bad(err instanceof Error ? err.message : "Import failed"));
  }

  async function runImport(prune: boolean) {
    if (!pendingImport) return;
    try {
      await applyImport(pendingImport.doc, prune);
      setPendingImport(null);
      await load();
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Import failed");
    }
  }
}
