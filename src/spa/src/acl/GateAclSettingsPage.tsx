import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "../chrome/toast";
import { FirewallPanel } from "../firewall/FirewallPanel";
import {
  clearFirewall,
  exportFirewall,
  fetchFirewall,
  fetchFirewallServices,
  importFirewall,
  putFirewall,
  type FirewallDocument,
  type FirewallServiceOption,
} from "../firewall/firewallApi";
import {
  clearGateAcl,
  fetchGateAcl,
  putGateAcl,
  type AclPolicy,
} from "./aclApi";
import { AclPanel } from "./AclPanel";
import "../deploy/DeployPage.css";
import "./GateAclSettingsPage.css";

/** Settings page: ordered firewall + legacy gate ACL. */
export function GateAclSettingsPage() {
  const [document, setDocument] = useState<FirewallDocument>({
    version: 1,
    rules: [],
  });
  const [services, setServices] = useState<FirewallServiceOption[]>([]);
  const [policy, setPolicy] = useState<AclPolicy>({ mode: "off", entries: [] });
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const [fw, svc, acl] = await Promise.all([
        fetchFirewall(),
        fetchFirewallServices(),
        fetchGateAcl(),
      ]);
      setDocument(fw);
      setServices(svc);
      setPolicy(acl);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load edge access",
      );
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
            Ordered firewall on the gate (Save → render → nginx reload). Legacy
            ACL remains until you adopt the firewall table.
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
        <>
          <FirewallPanel
            document={document}
            services={services}
            busy={busy}
            onSave={async (next) => {
              setDocument(await putFirewall(next));
            }}
            onExport={exportFirewall}
            onImport={async (body) => {
              setDocument(await importFirewall(body));
            }}
            onClear={async () => {
              try {
                setDocument(await clearFirewall());
                toast.good("Firewall cleared");
              } catch (err) {
                toast.bad(
                  err instanceof Error
                    ? err.message
                    : "Failed to clear firewall",
                );
              }
            }}
          />
          <AclPanel
            title="Legacy gate ACL"
            description="Flat whitelist/blacklist (#195). Still applied until you Save a firewall document (which supersedes ACL at render)."
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
                  err instanceof Error
                    ? err.message
                    : "Failed to clear gate ACL",
                );
              }
            }}
          />
        </>
      ) : null}
    </div>
  );
}
