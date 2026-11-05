import { useEffect, useState } from "react";
import { TemporaryOverrideBanner } from "../gitops/TemporaryOverrideBanner";
import { temporaryOverrideSavedMessage } from "../gitops/temporaryOverrideMessages";
import { toast } from "../chrome/toast/api";
import { RequirePermission } from "./RequirePermission";
import { getRbac, putRbac, type RbacDocument } from "./rbacApi";

export function RbacSettingsPage() {
  return (
    <RequirePermission permission="rbac:read">
      <RbacEditor />
    </RequirePermission>
  );
}

function RbacEditor() {
  const [doc, setDoc] = useState<RbacDocument | null>(null);
  const [yaml, setYaml] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getRbac()
      .then((d) => {
        setDoc(d);
        setYaml(JSON.stringify(d, null, 2));
      })
      .catch((err) => setError(String(err)));
  }, []);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const parsed = JSON.parse(yaml) as RbacDocument;
      const result = await putRbac(parsed);
      setDoc(result.document);
      setYaml(JSON.stringify(result.document, null, 2));
      toast.warning(temporaryOverrideSavedMessage("rbac.yaml"));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!doc && !error) return <p className="muted">Loading RBAC…</p>;

  return (
    <div className="page-block">
      <h1>RBAC</h1>
      <TemporaryOverrideBanner doc="rbac.yaml" />
      <p className="muted">
        Roles use resource:read / resource:write (+ *:read / *:write). Missing
        host/rbac.yaml bootstraps full admin. Edit durable copy in Git.
      </p>
      {error ? <p className="error">{error}</p> : null}
      <textarea
        className="code-block"
        rows={24}
        value={yaml}
        onChange={(e) => setYaml(e.target.value)}
        spellCheck={false}
      />
      <RequirePermission permission="rbac:write" fallback={null}>
        <p>
          <button
            type="button"
            className="btn"
            disabled={busy}
            onClick={() => void save()}
          >
            Save temporary override
          </button>
        </p>
      </RequirePermission>
    </div>
  );
}
