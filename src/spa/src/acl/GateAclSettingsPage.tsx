import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "../chrome/toast";
import {
  clearGateAcl,
  fetchGateAcl,
  putGateAcl,
  type AclPolicy,
} from "./aclApi";
import { AclPanel } from "./AclPanel";
import "../deploy/DeployPage.css";
import "./GateAclSettingsPage.css";

/** Settings page: gate-wide IP/CIDR whitelist/blacklist. */
export function GateAclSettingsPage() {
  const [policy, setPolicy] = useState<AclPolicy>({ mode: "off", entries: [] });
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setPolicy(await fetchGateAcl());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load gate ACL");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="page acl-gate-page">
      <header className="header">
        <div>
          <p className="brand">raft</p>
          <h1>Edge access</h1>
          <p className="muted header-updating">
            Gate-wide client IP/CIDR rules. Denied clients see a Forbidden page.
            Changes reload gate nginx (not recreate).
          </p>
        </div>
        <Link className="refresh" to="/" id="acl-gate-back">
          Stack status
        </Link>
      </header>

      {busy ? (
        <div className="loading" role="status" aria-busy="true">
          <span className="spinner" aria-hidden="true" />
          <p>Loading edge access…</p>
        </div>
      ) : null}

      {error ? (
        <p className="error" role="alert" id="acl-gate-error">
          {error}
        </p>
      ) : null}

      {!busy && !error ? (
        <AclPanel
          title="Gate ACL"
          description="Applies to the default edge listener and Host servers that inherit gate rules. Per-App ACL overrides gate when set."
          policy={policy}
          busy={busy}
          idPrefix="acl-gate"
          onSave={async (next) => {
            setPolicy(await putGateAcl(next));
          }}
          onClear={async () => {
            try {
              setPolicy(await clearGateAcl());
              toast.good("Gate ACL cleared");
            } catch (err) {
              toast.bad(
                err instanceof Error ? err.message : "Failed to clear gate ACL",
              );
            }
          }}
        />
      ) : null}
    </div>
  );
}
