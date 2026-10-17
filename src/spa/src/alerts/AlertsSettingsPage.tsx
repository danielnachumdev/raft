import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { LiveIndicator } from "../chrome/LiveIndicator";
import { toast } from "../chrome/toast";
import { PageHeader } from "../shell/PageHeader";
import { bindStatusPolling } from "../shell/statusPolling";
import {
  createAlertRule,
  deleteAlertRule,
  dryRunAlertRule,
  exportAlertRules,
  fetchAlertCatalog,
  fetchAlertRules,
  fetchAlertStatus,
  importAlertRules,
  replaceAlertRule,
  setAlertRuleEnabled,
  testAlertRule,
  catalogProxy,
  type AlertStatusPayload,
} from "./alertsApi";
import {
  emptyRuleDraft,
  relativeTime,
  routingLabel,
  ruleStateFor,
  summarizeCondition,
  validateDraft,
  type AlertCatalogPayload,
  type AlertRule,
} from "./alertsHelpers";
import { fetchNotificationChannels } from "../notifications/notificationsApi";
import type { NotificationChannel } from "../notifications/notificationsApi";
import "./AlertsSettingsPage.css";

export function AlertsSettingsPage() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [catalog, setCatalog] = useState<AlertCatalogPayload | null>(null);
  const [channels, setChannels] = useState<NotificationChannel[]>([]);
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [status, setStatus] = useState<AlertStatusPayload | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [draft, setDraft] = useState<AlertRule | null>(null);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [formError, setFormError] = useState<string | null>(null);
  const [formBusy, setFormBusy] = useState(false);
  const [now, setNow] = useState(Date.now());

  async function load() {
    setBusy(true);
    setError(null);
    try {
      await catalogProxy.refresh();
      const [rulesPayload, catalogPayload, channelPayload, statusPayload] =
        await Promise.all([
          fetchAlertRules(),
          fetchAlertCatalog(),
          fetchNotificationChannels(),
          fetchAlertStatus(),
        ]);
      setRules(rulesPayload.rules);
      setCatalog(catalogPayload);
      setChannels(channelPayload.channels);
      setNotificationsEnabled(channelPayload.enabled);
      setStatus(statusPayload);
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

  useEffect(() => {
    return bindStatusPolling(
      () => {
        void fetchAlertStatus()
          .then((payload) => {
            setStatus(payload);
            setNow(Date.now());
          })
          .catch(() => undefined);
      },
      setLive,
      10_000,
    );
  }, []);

  function openCreate() {
    if (!catalog) return;
    setFormMode("create");
    setDraft(emptyRuleDraft(catalog));
    setFormError(null);
    setFormOpen(true);
  }

  function openEdit(rule: AlertRule) {
    setFormMode("edit");
    setDraft({ ...rule });
    setFormError(null);
    setFormOpen(true);
  }

  async function saveRule() {
    if (!draft) return;
    const local = validateDraft(draft);
    if (local.length) {
      setFormError(local[0]);
      return;
    }
    setFormBusy(true);
    setFormError(null);
    try {
      if (formMode === "create") await createAlertRule(draft);
      else await replaceAlertRule(draft.id, draft);
      toast.good(formMode === "create" ? "Rule created" : "Rule saved");
      setFormOpen(false);
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Save failed";
      setFormError(message);
      toast.bad(message);
    } finally {
      setFormBusy(false);
    }
  }

  async function toggleEnabled(rule: AlertRule) {
    setBusyId(rule.id);
    try {
      await setAlertRuleEnabled(rule.id, !rule.enabled);
      await load();
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Toggle failed");
    } finally {
      setBusyId(null);
    }
  }

  async function removeRule(rule: AlertRule) {
    if (!window.confirm(`Delete alert rule ${rule.id}?`)) return;
    setBusyId(rule.id);
    try {
      await deleteAlertRule(rule.id);
      toast.good(`Deleted ${rule.id}`);
      await load();
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusyId(null);
    }
  }

  async function runDryRun(rule: AlertRule) {
    setBusyId(rule.id);
    try {
      const report = await dryRunAlertRule({ ruleId: rule.id });
      const matched = report.subjects.filter((s) => s.matched).length;
      toast.good(
        `Dry run ${rule.id}: ${matched}/${report.subjects.length} subjects matched`,
      );
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Dry run failed");
    } finally {
      setBusyId(null);
    }
  }

  async function sendTest(rule: AlertRule) {
    setBusyId(rule.id);
    try {
      const result = await testAlertRule(rule.id);
      if (result.ok) toast.good(result.message);
      else toast.bad(result.message);
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Test failed");
    } finally {
      setBusyId(null);
    }
  }

  async function onExport() {
    try {
      const doc = await exportAlertRules();
      const blob = new Blob([JSON.stringify(doc, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "raft-alerts.json";
      a.click();
      URL.revokeObjectURL(url);
      toast.good("Alerts exported");
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Export failed");
    }
  }

  async function onImport(file: File) {
    try {
      const text = await file.text();
      const document = JSON.parse(text) as { version: number; rules: AlertRule[] };
      const prune = window.confirm(
        "Replace existing rules absent from the file? OK = replace, Cancel = merge",
      );
      await importAlertRules(document, prune);
      toast.good("Alerts imported");
      await load();
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Import failed");
    }
  }

  const enabledChannels = channels.filter((c) => c.enabled);
  const interval = status?.intervalSeconds ?? 60;

  return (
    <div className="alerts-page" id="alerts-page">
      <PageHeader
        title="Alerts"
        subtitle="Rules that watch metrics and control-plane signals and send through your notification channels."
        meta={
          <>
            <span className="chip">
              {status?.enabled === false
                ? "Alerts disabled in settings.yaml"
                : `Evaluating every ${interval}s`}
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
            <button
              type="button"
              className="btn-primary"
              id="alerts-add"
              disabled={busy || !catalog}
              onClick={openCreate}
            >
              Add rule
            </button>
            <button type="button" className="btn" onClick={() => void onExport()}>
              Export
            </button>
            <label className="btn">
              Import
              <input
                type="file"
                accept="application/json,.json,.yaml,.yml"
                hidden
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void onImport(file);
                  e.target.value = "";
                }}
              />
            </label>
          </>
        }
      />

      {busy ? (
        <div className="loading">
          <span className="spinner" aria-hidden /> Loading alerts…
        </div>
      ) : null}
      {error ? (
        <p className="error" id="alerts-error" role="alert">
          {error}{" "}
          <button type="button" className="btn" onClick={() => void load()}>
            Retry
          </button>
        </p>
      ) : null}
      {status?.stale ? (
        <div className="callout callout-warn" id="alerts-stale">
          The controller has not evaluated alerts recently. Run `raft doctor`.
        </div>
      ) : null}
      {status?.documentError ? (
        <div className="callout callout-bad" id="alerts-document-error">
          {status.documentError}
        </div>
      ) : null}
      {!enabledChannels.length ? (
        <div className="callout callout-warn" id="alerts-no-channels">
          Alerts will evaluate but nothing will be delivered. Add a channel in{" "}
          <Link to="/settings/notifications">Notifications</Link>.
        </div>
      ) : null}

      <section className="panel" id="alerts-status">
        <h2>
          Currently firing{" "}
          <span className="muted">
            ({status?.instances.filter((i) => i.state === "firing").length ?? 0})
          </span>
        </h2>
        {status?.lastEvaluation?.finishedAt ? (
          <p className="muted">
            Last evaluated{" "}
            {relativeTime(String(status.lastEvaluation.finishedAt), now)}
            {typeof status.lastEvaluation.durationMs === "number"
              ? ` · ${status.lastEvaluation.durationMs} ms`
              : null}
          </p>
        ) : (
          <p className="muted">
            Waiting for the first evaluation (controller runs every {interval}s).
          </p>
        )}
        {!status?.instances?.length ? (
          <div className="empty-state" id="alerts-none-firing">
            Nothing firing.
          </div>
        ) : (
          <ul className="alert-instance-list">
            {status.instances.map((inst) => (
              <li key={inst.fingerprint}>
                <span
                  className={
                    inst.state === "firing" ? "chip chip-bad" : "chip chip-warn"
                  }
                >
                  {inst.suppressed ? "suppressed" : inst.state}
                </span>{" "}
                <strong>{inst.ruleName}</strong> · {inst.subject}
                {inst.since ? ` · since ${relativeTime(inst.since, now)}` : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel" id="alerts-rules">
        <h2>Rules</h2>
        {!rules.length ? (
          <div className="empty-state" id="alerts-empty">
            <p>
              <strong>No alert rules yet.</strong>
            </p>
            <p className="muted">
              Use <em>Add rule</em>, or `raft alerts apply --file rules.yaml` on
              the host.
            </p>
          </div>
        ) : (
          <ul className="alert-rule-list">
            {rules.map((rule) => {
              const state = ruleStateFor(status, rule.id, rule.enabled);
              return (
                <li
                  key={rule.id}
                  className="alert-rule-row"
                  data-rule-id={rule.id}
                  id={`alert-rule-${rule.id}`}
                >
                  <div className="alert-rule-main">
                    <div>
                      <strong>{rule.name}</strong>{" "}
                      <code>{rule.id}</code>
                    </div>
                    <div className="muted">
                      <span
                        className={
                          state === "firing"
                            ? "chip chip-bad"
                            : state === "pending" || state === "suppressed"
                              ? "chip chip-warn"
                              : state === "ok"
                                ? "chip chip-ok"
                                : "chip"
                        }
                      >
                        {state}
                      </span>{" "}
                      <span className="chip">{rule.severity}</span>{" "}
                      {summarizeCondition(rule.condition, catalog ?? undefined)}{" "}
                      · for {rule.for} · cool-down {rule.cooldown} ·{" "}
                      {routingLabel(rule.channelIds, channels)}
                    </div>
                  </div>
                  <div className="alert-rule-actions">
                    <button
                      type="button"
                      className="action-btn"
                      id={`alert-toggle-${rule.id}`}
                      disabled={busyId === rule.id}
                      onClick={() => void toggleEnabled(rule)}
                    >
                      {rule.enabled ? "Disable" : "Enable"}
                    </button>
                    <button
                      type="button"
                      className="action-btn"
                      id={`alert-edit-${rule.id}`}
                      onClick={() => openEdit(rule)}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="action-btn"
                      id={`alert-dryrun-${rule.id}`}
                      disabled={busyId === rule.id}
                      onClick={() => void runDryRun(rule)}
                    >
                      Dry run
                    </button>
                    <button
                      type="button"
                      className="action-btn"
                      id={`alert-test-${rule.id}`}
                      disabled={busyId === rule.id || !enabledChannels.length}
                      title={
                        enabledChannels.length
                          ? undefined
                          : "No deliverable channel"
                      }
                      onClick={() => void sendTest(rule)}
                    >
                      Send test
                    </button>
                    <button
                      type="button"
                      className="action-btn action-btn-danger"
                      id={`alert-delete-${rule.id}`}
                      disabled={busyId === rule.id}
                      onClick={() => void removeRule(rule)}
                    >
                      Delete
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {formOpen && draft ? (
        <div className="modal-overlay" role="presentation">
          <div
            className="modal modal-wide"
            role="dialog"
            aria-labelledby="alert-form-title"
          >
            <h2 id="alert-form-title">
              {formMode === "create" ? "Add alert rule" : "Edit alert rule"}
            </h2>
            <form
              id="alert-rule-form"
              onSubmit={(e) => {
                e.preventDefault();
                void saveRule();
              }}
            >
              <label>
                Id
                <input
                  id="alert-id"
                  value={draft.id}
                  disabled={formMode === "edit" || formBusy}
                  onChange={(e) => setDraft({ ...draft, id: e.target.value })}
                />
              </label>
              <label>
                Name
                <input
                  value={draft.name}
                  disabled={formBusy}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                />
              </label>
              <label>
                Severity
                <select
                  value={draft.severity}
                  disabled={formBusy}
                  onChange={(e) =>
                    setDraft({ ...draft, severity: e.target.value })
                  }
                >
                  {(catalog?.severities ?? []).map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={draft.enabled}
                  disabled={formBusy}
                  onChange={(e) =>
                    setDraft({ ...draft, enabled: e.target.checked })
                  }
                />
                Enabled
              </label>
              <label>
                Description
                <textarea
                  value={draft.description}
                  disabled={formBusy}
                  onChange={(e) =>
                    setDraft({ ...draft, description: e.target.value })
                  }
                />
              </label>
              <label>
                For
                <input
                  value={draft.for}
                  disabled={formBusy}
                  onChange={(e) => setDraft({ ...draft, for: e.target.value })}
                />
              </label>
              <label>
                Cool-down
                <input
                  value={draft.cooldown}
                  disabled={formBusy}
                  onChange={(e) =>
                    setDraft({ ...draft, cooldown: e.target.value })
                  }
                />
              </label>
              <p className="muted">
                Condition JSON (advanced): edit via CLI for nested groups in v1
                UI polish.
              </p>
              <textarea
                value={JSON.stringify(draft.condition, null, 2)}
                disabled={formBusy}
                rows={8}
                onChange={(e) => {
                  try {
                    setDraft({
                      ...draft,
                      condition: JSON.parse(e.target.value) as AlertRule["condition"],
                    });
                  } catch {
                    /* keep typing */
                  }
                }}
              />
              {formError ? (
                <p className="error" id="alert-form-error">
                  {formError}
                </p>
              ) : null}
              <div className="modal-actions">
                <button
                  type="button"
                  className="btn"
                  disabled={formBusy}
                  onClick={() => setFormOpen(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={`btn-primary${formBusy ? " is-loading" : ""}`}
                  disabled={formBusy}
                >
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
