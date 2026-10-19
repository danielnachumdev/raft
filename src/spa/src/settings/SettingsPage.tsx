import { useCallback, useEffect, useState } from "react";
import { toast } from "../chrome/toast";
import { PageHeader } from "../shell/PageHeader";
import {
  fetchSettings,
  putSettings,
  type SettingsDocument,
  type SettingsNote,
} from "./settingsApi";
import { SettingsNotes } from "./SettingsNotes";
import {
  AcmeSection,
  AlertsSection,
  AppearanceSection,
  EdgeSection,
  GithubSection,
  HealingSection,
  LoggingSection,
  MetricsSection,
  NotificationsSection,
  ServiceLogsSection,
  StorageSection,
} from "./sections";
import "./SettingsPage.css";

/** Full ``settings.yaml`` / RaftConfig editor for ``raft serve``. */
export function SettingsPage() {
  const [draft, setDraft] = useState<SettingsDocument | null>(null);
  const [path, setPath] = useState("");
  const [notes, setNotes] = useState<SettingsNote[]>([]);
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const payload = await fetchSettings();
      setDraft(structuredClone(payload.document));
      setPath(payload.path);
      setNotes(payload.notes);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load settings");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    setError(null);
    try {
      const payload = await putSettings(draft);
      setDraft(structuredClone(payload.document));
      setPath(payload.path);
      setNotes(payload.notes);
      const warn = payload.notes.find((n) => n.severity === "warn");
      if (warn) toast.warning(warn.message);
      else toast.good("Settings saved");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to save settings";
      setError(message);
      toast.bad(message);
    } finally {
      setSaving(false);
    }
  };

  const patch = <K extends keyof SettingsDocument>(
    key: K,
    value: SettingsDocument[K],
  ) => {
    setDraft((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  return (
    <div className="settings-page">
      <PageHeader
        title="Settings"
        subtitle="Operator settings.yaml for this host — logging, edge, healing, metrics, and more."
        meta={
          path ? (
            <code className="settings-path" title={path}>
              {path}
            </code>
          ) : undefined
        }
        actions={
          <>
            <button
              type="button"
              className="btn-secondary"
              id="settings-reload"
              disabled={busy || saving}
              onClick={() => void load()}
            >
              Reload
            </button>
            <button
              type="button"
              className="btn-primary"
              id="settings-save"
              disabled={busy || saving || !draft}
              onClick={() => void save()}
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </>
        }
      />

      <AppearanceSection />

      {busy ? (
        <div className="loading" role="status" aria-busy="true">
          <span className="spinner" aria-hidden="true" />
          <p>Loading settings…</p>
        </div>
      ) : null}

      {error ? (
        <p className="error" role="alert" id="settings-error">
          {error}
        </p>
      ) : null}

      {!busy && draft ? (
        <>
          <SettingsNotes notes={notes} />
          <nav className="settings-toc" aria-label="Settings sections">
            {TOC.map((item) => (
              <a key={item.href} href={item.href}>
                {item.label}
              </a>
            ))}
          </nav>
          <LoggingSection
            value={draft.logging}
            onChange={(logging) => patch("logging", logging)}
          />
          <EdgeSection
            value={draft.edge}
            onChange={(edge) => patch("edge", edge)}
          />
          <HealingSection
            value={draft.healing}
            onChange={(healing) => patch("healing", healing)}
          />
          <MetricsSection
            value={draft.metrics}
            onChange={(metrics) => patch("metrics", metrics)}
          />
          <ServiceLogsSection
            value={draft.serviceLogs}
            onChange={(serviceLogs) => patch("serviceLogs", serviceLogs)}
          />
          <AcmeSection
            value={draft.acme}
            onChange={(acme) => patch("acme", acme)}
          />
          <GithubSection
            value={draft.github}
            onChange={(github) => patch("github", github)}
          />
          <NotificationsSection
            value={draft.notifications}
            onChange={(notifications) => patch("notifications", notifications)}
          />
          <AlertsSection
            value={draft.alerts}
            onChange={(alerts) => patch("alerts", alerts)}
          />
          <StorageSection />
        </>
      ) : null}
    </div>
  );
}

const TOC = [
  { href: "#settings-appearance", label: "Appearance" },
  { href: "#settings-logging", label: "Logging" },
  { href: "#settings-edge", label: "Edge" },
  { href: "#settings-healing", label: "Healing" },
  { href: "#settings-metrics", label: "Metrics" },
  { href: "#settings-service-logs", label: "Service logs" },
  { href: "#settings-acme", label: "ACME" },
  { href: "#settings-github", label: "GitHub" },
  { href: "#settings-notifications", label: "Notifications" },
  { href: "#settings-alerts", label: "Alerts" },
  { href: "#settings-storage", label: "Storage" },
];
