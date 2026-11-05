import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import {
  FIREWALL_TABLE_BONE_WIDTHS,
  FIREWALL_TABLE_SKELETON_COLUMNS,
  SectionPanelSkeleton,
  showSkeleton,
  SkeletonRoot,
  StatusTableSkeleton,
} from "../chrome/skeleton";
import { ErrorState } from "../chrome/StateViews";
import { useHashScroll } from "../chrome/useHashScroll";
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
  const { hash } = useLocation();
  const [document, setDocument] = useState<FirewallDocument>({
    version: 1,
    rules: [],
  });
  const [services, setServices] = useState<FirewallServiceOption[]>([]);
  const [recommendations, setRecommendations] = useState<
    FirewallRecommendation[]
  >([]);
  const [busy, setBusy] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useHashScroll(hash, loaded && error === null);

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
      setLoaded(true);
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
      subtitle="Ordered edge rules (first match wins). Saving applies them without recreating the gate — as a temporary host override until the next GitOps sync. ACME HTTP-01 sits outside these rules; still avoid a broad port-80 deny/drop on service any if you use Let's Encrypt."
      actions={actions}
    />
  );

  if (showSkeleton(busy, loaded)) {
    return (
      <>
        {header()}
        <SkeletonRoot label="Loading firewall…" id="firewall-loading">
          <SectionPanelSkeleton titleWidth="3.5rem" id="firewall-rules-skeleton">
            <StatusTableSkeleton
              rows={5}
              columns={FIREWALL_TABLE_SKELETON_COLUMNS}
              boneWidths={FIREWALL_TABLE_BONE_WIDTHS}
            />
          </SectionPanelSkeleton>
        </SkeletonRoot>
      </>
    );
  }

  if (error && !loaded) {
    return (
      <>
        {header()}
        <ErrorState
          message={error}
          id="firewall-page-error"
          onRetry={() => void load()}
        />
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
