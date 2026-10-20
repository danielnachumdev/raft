import { useCallback, useEffect, useState } from "react";
import { toast } from "../chrome/toast";
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
import { settingsDirty } from "./settingsLayout";

export type EditorMode = "form" | "yaml";

type Payload = {
  path: string;
  document: SettingsDocument;
  sections: SettingsSection[];
  notes: SettingsNote[];
  yaml?: string;
};

/** Load / edit / save state for the Settings page (form + YAML modes). */
export function useSettingsEditor() {
  const [draft, setDraft] = useState<SettingsDocument | null>(null);
  const [savedJson, setSavedJson] = useState("");
  const [sections, setSections] = useState<SettingsSection[]>([]);
  const [enabled, setEnabled] = useState<EnabledMap>({});
  const [yamlText, setYamlText] = useState("");
  const [yamlBaseline, setYamlBaseline] = useState("");
  const [mode, setMode] = useState<EditorMode>("form");
  const [path, setPath] = useState("");
  const [notes, setNotes] = useState<SettingsNote[]>([]);
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const applyPayload = useCallback((payload: Payload) => {
    setDraft(structuredClone(payload.document));
    setSavedJson(JSON.stringify(payload.document));
    setSections(payload.sections);
    setEnabled(enabledMapFromSections(payload.sections));
    setPath(payload.path);
    setNotes(payload.notes);
    if (payload.yaml != null) {
      setYamlText(payload.yaml);
      setYamlBaseline(payload.yaml);
    }
  }, []);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      applyPayload(await fetchSettings());
      setMode("form");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load settings");
    } finally {
      setBusy(false);
    }
  }, [applyPayload]);

  useEffect(() => {
    void load();
  }, [load]);

  const fail = (err: unknown, fallback: string) => {
    const message = err instanceof Error ? err.message : fallback;
    setError(message);
    toast.bad(message);
  };

  const switchMode = async (next: EditorMode) => {
    if (next === mode || !draft) return;
    setError(null);
    try {
      if (next === "yaml") {
        const encoded = await encodeSettingsYaml(draft);
        setYamlText(encoded.yaml);
        setYamlBaseline(encoded.yaml);
      } else {
        const decoded = await decodeSettingsYaml(yamlText);
        setDraft(structuredClone(decoded.document));
        setSections(decoded.sections);
        setEnabled(enabledMapFromSections(decoded.sections));
      }
      setMode(next);
    } catch (err) {
      fail(err, "Failed to switch editor mode");
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

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload =
        mode === "yaml" ? await putSettingsYaml(yamlText) : await saveForm();
      if (!payload) return;
      applyPayload(payload);
      if (mode === "yaml") setYamlBaseline(payload.yaml ?? yamlText);
      const warn = payload.notes.find((n) => n.severity === "warn");
      if (warn) toast.warning(warn.message);
      else toast.good("Settings saved");
    } catch (err) {
      fail(err, "Failed to save settings");
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

  const setSectionEnabled = (key: string, next: boolean) => {
    setEnabled((prev) => ({ ...prev, [key]: next }));
    setDraft((prev) => (prev ? applySectionEnabled(prev, key, next) : prev));
  };

  const dirty = settingsDirty({ mode, draft, savedJson, yamlText, yamlBaseline });

  return {
    draft, sections, enabled, yamlText, setYamlText, mode, path, notes,
    busy, saving, error, dirty,
    load, switchMode, save, patch, setSectionEnabled,
  };
}
