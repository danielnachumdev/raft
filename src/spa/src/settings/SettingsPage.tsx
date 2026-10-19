import { useCallback, useEffect, useState } from "react";
import { toast } from "../chrome/toast";
import { PageHeader } from "../shell/PageHeader";
import { AppearanceSection } from "./sections/AppearanceSection";
import { UpdatesSection } from "./sections/UpdatesSection";
import { SettingsFormView } from "./SettingsFormView";
import { SettingsNotes } from "./SettingsNotes";
import { SettingsYamlPanel } from "./SettingsYamlPanel";
import {
  applySectionEnabled,
  enabledMapFromSections,
  validateEnabledSections,
  type EnabledMap,
} from "./sectionEnablement";
import {
  decodeSettingsYaml,
  encodeSettingsYaml,
  fetchSettings,
  putSettings,
  putSettingsYaml,
  type SettingsDocument,
  type SettingsNote,
  type SettingsSection,
} from "./settingsApi";
import "./SettingsPage.css";

type EditorMode = "form" | "yaml";

/** Full ``settings.yaml`` / RaftConfig editor for ``raft serve``. */
export function SettingsPage() {
  const [draft, setDraft] = useState<SettingsDocument | null>(null);
  const [sections, setSections] = useState<SettingsSection[]>([]);
  const [enabled, setEnabled] = useState<EnabledMap>({});
  const [yamlText, setYamlText] = useState("");
  const [mode, setMode] = useState<EditorMode>("form");
  const [path, setPath] = useState("");
  const [notes, setNotes] = useState<SettingsNote[]>([]);
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const applyPayload = useCallback(
    (payload: {
      path: string;
      document: SettingsDocument;
      sections: SettingsSection[];
      notes: SettingsNote[];
      yaml?: string;
    }) => {
      setDraft(structuredClone(payload.document));
      setSections(payload.sections);
      setEnabled(enabledMapFromSections(payload.sections));
      setPath(payload.path);
      setNotes(payload.notes);
      if (payload.yaml != null) setYamlText(payload.yaml);
    },
    [],
  );

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      applyPayload(await fetchSettings());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load settings");
    } finally {
      setBusy(false);
    }
  }, [applyPayload]);

  useEffect(() => {
    void load();
  }, [load]);

  const switchMode = async (next: EditorMode) => {
    if (next === mode || !draft) return;
    setError(null);
    try {
      if (next === "yaml") {
        const encoded = await encodeSettingsYaml(draft);
        setYamlText(encoded.yaml);
        setMode("yaml");
        return;
      }
      const decoded = await decodeSettingsYaml(yamlText);
      setDraft(structuredClone(decoded.document));
      setSections(decoded.sections);
      setEnabled(enabledMapFromSections(decoded.sections));
      setMode("form");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to switch editor mode";
      setError(message);
      toast.bad(message);
    }
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload =
        mode === "yaml" ? await putSettingsYaml(yamlText) : await saveForm();
      if (!payload) return;
      applyPayload(payload);
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

  const saveForm = async () => {
    if (!draft) return null;
    const problem = validateEnabledSections(draft, enabled);
    if (problem) {
      setError(problem);
      toast.bad(problem);
      return null;
    }
    return putSettings(draft);
  };

  const patch = <K extends keyof SettingsDocument>(
    key: K,
    value: SettingsDocument[K],
  ) => {
    setDraft((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const onEnabledChange = (key: string, next: boolean) => {
    setEnabled((prev) => ({ ...prev, [key]: next }));
    setDraft((prev) =>
      prev ? applySectionEnabled(prev, key, next) : prev,
    );
  };

  return (
    <div className="settings-page">
      <PageHeader
        title="Settings"
        subtitle="Operator settings.yaml — enable sections, edit as form or YAML."
        meta={
          path ? (
            <code className="settings-path" title={path}>
              {path}
            </code>
          ) : undefined
        }
        actions={
          <>
            <div className="settings-mode" role="tablist" aria-label="Editor mode">
              <button
                type="button"
                role="tab"
                id="settings-mode-form"
                className={mode === "form" ? "btn-primary" : "btn-secondary"}
                aria-selected={mode === "form"}
                disabled={busy || saving}
                onClick={() => void switchMode("form")}
              >
                Form
              </button>
              <button
                type="button"
                role="tab"
                id="settings-mode-yaml"
                className={mode === "yaml" ? "btn-primary" : "btn-secondary"}
                aria-selected={mode === "yaml"}
                disabled={busy || saving || !draft}
                onClick={() => void switchMode("yaml")}
              >
                YAML
              </button>
            </div>
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
              disabled={busy || saving || (mode === "form" && !draft)}
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
          {mode === "form" ? (
            <>
              <UpdatesSection />
              <SettingsFormView
                draft={draft}
                sections={sections}
                enabled={enabled}
                onPatch={patch}
                onEnabledChange={onEnabledChange}
              />
            </>
          ) : (
            <SettingsYamlPanel
              value={yamlText}
              onChange={setYamlText}
              disabled={saving}
            />
          )}
        </>
      ) : null}
    </div>
  );
}
