import { useCallback, useEffect, useState, type ReactNode } from "react";
import { ErrorState, LoadingState } from "../chrome/StateViews";
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

  const header = (actions?: ReactNode) => (
    <PageHeader
      title="Firewall"
      subtitle="Ordered edge rules on the gate (first match wins). Saving compiles them and reloads gate nginx — the gate is never recreated. ACME HTTP-01 sits outside these locations; still avoid a broad port-80 deny/drop on service any if you use Let's Encrypt."
      actions={actions}
    />
  );

  if (busy || error) {
    return (
      <>
        {header()}
        {busy ? <LoadingState label="Loading firewall…" /> : null}
        {error ? (
          <ErrorState
            message={error}
            id="firewall-page-error"
            onRetry={() => void load()}
          />
        ) : null}
      </>
    );
  }

  return (
    <FirewallPanel
      document={document}
      services={services}
      recommendations={recommendations}
      busy={busy}
      header={header}
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
  );
}
