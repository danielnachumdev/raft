import { useEffect, useState } from "react";
import { ErrorState, LoadingState } from "../chrome/StateViews";
import { toast } from "../chrome/toast";
import {
  TemporaryOverrideBanner,
  temporaryOverrideSavedMessage,
} from "../gitops";
import { PageHeader } from "../shell/PageHeader";
import { RequirePermission } from "./RequirePermission";
import { getRbac, putRbac, type RbacDocument } from "./rbacApi";
import "./RbacSettingsPage.css";

/** Temporary-override editor for ``host/rbac.yaml`` roles and bindings. */
export function RbacSettingsPage() {
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

  const loading = !doc && !error;

  return (
    <div className="rbac-page">
      <PageHeader
        title="RBAC"
        subtitle="Roles use resource:read / resource:write (+ *:read / *:write). Missing host/rbac.yaml bootstraps full admin. Edit durable copy in Git."
        actions={
          loading ? undefined : (
            <RequirePermission permission="rbac:write" fallback={null}>
              <button
                type="button"
                className={busy ? "btn btn-primary is-loading" : "btn btn-primary"}
                id="rbac-save"
                disabled={busy}
                aria-busy={busy}
                onClick={() => void save()}
              >
                Save temporary override
              </button>
            </RequirePermission>
          )
        }
      />

      {loading ? <LoadingState label="Loading RBAC…" id="rbac-loading" /> : null}

      {error ? <ErrorState message={error} id="rbac-error" /> : null}

      {loading ? null : (
        <>
          <TemporaryOverrideBanner doc="rbac.yaml" id="rbac-temp-override" />
          <section className="panel" id="rbac-document">
            <label className="field rbac-field" htmlFor="rbac-editor">
              JSON
              <textarea
                id="rbac-editor"
                className="rbac-editor"
                rows={24}
                value={yaml}
                onChange={(e) => setYaml(e.target.value)}
                spellCheck={false}
              />
            </label>
          </section>
        </>
      )}
    </div>
  );
}
