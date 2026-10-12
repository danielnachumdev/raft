import { useCallback, useEffect, useState } from "react";
import { toast } from "../chrome/toast";
import {
  clearAppAcl,
  fetchAppAcl,
  fetchAppAclMeta,
  putAppAcl,
  type AclAppMeta,
  type AclPolicy,
} from "./aclApi";
import { AclPanel } from "./AclPanel";

type Props = {
  service: string;
  appName: string | null | undefined;
};

/** Per-App ACL on service detail (HTTP Host-routed Apps only). */
export function ServiceAclPanel(props: Props) {
  const name = props.appName || props.service;
  const [meta, setMeta] = useState<AclAppMeta | null>(null);
  const [policy, setPolicy] = useState<AclPolicy>({ mode: "off", entries: [] });
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const nextMeta = await fetchAppAclMeta(name);
      setMeta(nextMeta);
      if (!nextMeta.supported) {
        setPolicy({ mode: "off", entries: [] });
        return;
      }
      setPolicy(await fetchAppAcl(name));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load app ACL");
    } finally {
      setBusy(false);
    }
  }, [name]);

  useEffect(() => {
    void load();
  }, [load]);

  if (busy) {
    return (
      <section className="panel" id="service-acl-loading">
        <h2>Access control</h2>
        <p className="muted">Loading ACL…</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="panel" id="service-acl-error">
        <h2>Access control</h2>
        <p className="error" role="alert">
          {error}
        </p>
      </section>
    );
  }

  if (meta && !meta.supported) {
    return (
      <section className="panel" id="service-acl-unsupported">
        <h2>Access control</h2>
        <p className="muted">
          {meta.reason || "ACL is not available for this service."}
        </p>
        {meta.fix ? <p className="muted">Fix: {meta.fix}</p> : null}
      </section>
    );
  }

  return (
    <AclPanel
      title="Access control"
      description={`Client IP/CIDR rules for ${name} (Host-routed HTTP). Overrides gate ACL when active.`}
      policy={policy}
      busy={busy}
      idPrefix="service-acl"
      onSave={async (next) => {
        setPolicy(await putAppAcl(name, next));
      }}
      onClear={async () => {
        try {
          setPolicy(await clearAppAcl(name));
          toast.good("App ACL cleared");
        } catch (err) {
          toast.bad(
            err instanceof Error ? err.message : "Failed to clear app ACL",
          );
        }
      }}
    />
  );
}
