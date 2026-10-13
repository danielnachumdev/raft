import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FirewallPanel } from "./FirewallPanel";
import {
  dismissFirewallRecommendation,
  exportFirewall,
  fetchFirewall,
  fetchFirewallRecommendations,
  fetchFirewallServices,
  importFirewall,
  putFirewall,
  type FirewallDocument,
  type FirewallRecommendation,
  type FirewallServiceOption,
} from "./firewallApi";
import "../deploy/DeployPage.css";
import "./FirewallSettingsPage.css";

/** Settings page: ordered edge firewall only. */
export function FirewallSettingsPage() {
  const [document, setDocument] = useState<FirewallDocument>({
    version: 1,
    rules: [],
  });
  const [services, setServices] = useState<FirewallServiceOption[]>([]);
  const [recommendations, setRecommendations] = useState<
    FirewallRecommendation[]
  >([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const [fw, svc, recs] = await Promise.all([
        fetchFirewall(),
        fetchFirewallServices(),
        fetchFirewallRecommendations(),
      ]);
      setDocument(fw);
      setServices(svc);
      setRecommendations(recs);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load firewall",
      );
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="page fw-settings-page">
      <header className="header">
        <div>
          <p className="brand">raft</p>
          <h1>Firewall</h1>
          <p className="muted header-updating">
            Ordered rules on the gate. Save compiles and reloads nginx — never
            recreate.
          </p>
        </div>
        <Link className="refresh" to="/" id="firewall-back">
          Stack status
        </Link>
      </header>

      {busy ? (
        <div className="loading" role="status" aria-busy="true">
          <span className="spinner" aria-hidden="true" />
          <p>Loading firewall…</p>
        </div>
      ) : null}

      {error ? (
        <p className="error" role="alert" id="firewall-page-error">
          {error}
        </p>
      ) : null}

      {!busy && !error ? (
        <FirewallPanel
          document={document}
          services={services}
          recommendations={recommendations}
          busy={busy}
          onSave={async (next) => {
            setDocument(await putFirewall(next));
            setRecommendations(await fetchFirewallRecommendations());
          }}
          onExport={exportFirewall}
          onImport={async (body) => {
            setDocument(await importFirewall(body));
            setRecommendations(await fetchFirewallRecommendations());
          }}
          onDismissRecommendation={async (id) => {
            setRecommendations(await dismissFirewallRecommendation(id));
          }}
        />
      ) : null}
    </div>
  );
}
