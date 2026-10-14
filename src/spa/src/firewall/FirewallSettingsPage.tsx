import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "../shell/PageHeader";
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
    <div className="fw-settings-page">
      <PageHeader
        title="Firewall"
        subtitle="Ordered edge rules on the gate. Saving compiles them and reloads gate nginx — the gate is never recreated."
      />

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
