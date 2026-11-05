import { useCallback, useEffect, useState } from "react";
import { toast } from "../../shared/chrome/toast";
import { temporaryOverrideSavedMessage } from "../../shared/gitops";
import {
  decodeRbacYaml,
  encodeRbacYaml,
  getRbac,
  getRbacCatalog,
  putRbac,
  type RbacDocument,
} from "./rbacApi";
import {
  ensureAdminRole,
  rbacDirty,
  type EditorMode,
} from "./rbacDocument";

/** Load / edit / save state for the RBAC page (form + YAML modes). */
export function useRbacEditor() {
  const [draft, setDraft] = useState<RbacDocument | null>(null);
  const [savedJson, setSavedJson] = useState("");
  const [catalog, setCatalog] = useState<string[]>([]);
  const [yamlText, setYamlText] = useState("");
  const [yamlBaseline, setYamlBaseline] = useState("");
  const [mode, setMode] = useState<EditorMode>("form");
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const applyDocument = useCallback((document: RbacDocument) => {
    const next = ensureAdminRole(structuredClone(document));
    setDraft(next);
    setSavedJson(JSON.stringify(next));
  }, []);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const [document, permissions] = await Promise.all([
        getRbac(),
        getRbacCatalog(),
      ]);
      applyDocument(document);
      setCatalog(permissions);
      setMode("form");
      setYamlText("");
      setYamlBaseline("");
    } catch (err) {
      if (err instanceof Error) console.error(err);
      setError("Failed to load access settings.");
    } finally {
      setBusy(false);
    }
  }, [applyDocument]);

  useEffect(() => {
    void load();
  }, [load]);

  const fail = (err: unknown, fallback: string) => {
    if (err instanceof Error) console.error(err);
    setError(fallback);
    toast.bad(fallback);
  };

  const switchMode = async (next: EditorMode) => {
    if (next === mode || !draft) return;
    setError(null);
    try {
      if (next === "yaml") {
        const encoded = await encodeRbacYaml(draft);
        setYamlText(encoded.yaml);
        setYamlBaseline(encoded.yaml);
      } else {
        const decoded = await decodeRbacYaml(yamlText);
        setDraft(ensureAdminRole(structuredClone(decoded.document)));
      }
      setMode(next);
    } catch (err) {
      fail(err, "Failed to switch editor mode.");
    }
  };

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    setError(null);
    try {
      const document =
        mode === "yaml"
          ? (await decodeRbacYaml(yamlText)).document
          : ensureAdminRole(draft);
      const result = await putRbac(document);
      applyDocument(result.document);
      if (mode === "yaml") {
        const encoded = await encodeRbacYaml(result.document);
        setYamlText(encoded.yaml);
        setYamlBaseline(encoded.yaml);
      }
      toast.warning(temporaryOverrideSavedMessage("rbac.yaml"));
    } catch (err) {
      fail(err, "Failed to save access settings.");
    } finally {
      setSaving(false);
    }
  };

  const setDocument = (next: RbacDocument) => {
    setDraft(ensureAdminRole(next));
  };

  const dirty = rbacDirty({ mode, draft, savedJson, yamlText, yamlBaseline });

  return {
    draft,
    catalog,
    yamlText,
    setYamlText,
    mode,
    busy,
    saving,
    error,
    dirty,
    load,
    switchMode,
    save,
    setDocument,
  };
}
