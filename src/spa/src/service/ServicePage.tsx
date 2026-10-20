import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import {
  documentTitleForHost,
  fetchService,
  type ServiceDetailPayload,
} from "../shared/api";
import {
  invalidateMetrics,
  invalidateStatus,
  refreshStatus,
} from "../shared/dashboardCache";
import { ExternalUrlLinks } from "../shared/ExternalUrlLinks";
import { ErrorState, LoadingState } from "../chrome/StateViews";
import { useHashScroll } from "../chrome/useHashScroll";
import { PageHeader } from "../shell/PageHeader";
import { StatusBadge } from "../status/StatusBadge";
import { ServiceActions } from "./ServiceActions";
import { ServiceDetail } from "./ServiceDetail";
import "./ServicePage.css";

/** Deep-linked service page: `/service/:service`. */
export function ServicePage() {
  const { service: raw } = useParams<{ service: string }>();
  const service = raw ? decodeURIComponent(raw) : "";
  const { hash } = useLocation();
  const [data, setData] = useState<ServiceDetailPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [trendsKey, setTrendsKey] = useState(0);

  const load = useCallback(async () => {
    if (!service) {
      setError("Missing service name.");
      setBusy(false);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setData(await fetchService(service));
    } catch (err) {
      setData(null);
      setError(err instanceof Error && err.message === "not found"
        ? `Service '${service}' was not found in the current status snapshot.`
        : "Failed to load service detail.");
    } finally {
      setBusy(false);
    }
  }, [service]);

  useEffect(() => {
    void load();
  }, [load]);

  const onActionDone = useCallback(async () => {
    await load();
    try {
      await refreshStatus();
    } catch {
      invalidateStatus();
    }
    invalidateMetrics();
    setTrendsKey((k) => k + 1);
  }, [load]);

  useEffect(() => {
    const label = data?.presentation.name ?? service;
    document.title = label
      ? `raft - ${label}`
      : documentTitleForHost(data?.host?.hostname);
  }, [data, service]);

  useHashScroll(hash, data !== null);

  const p = data?.presentation;
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Status", to: "/" }]}
        title={(p?.name ?? service) || "Service"}
        meta={p ? <ServiceMeta data={data!} /> : undefined}
        actions={
          data ? (
            <ServiceActions
              service={data.container.service}
              status={data.container.status}
              onDone={() => void onActionDone()}
            />
          ) : undefined
        }
      />

      {busy && data === null && !error ? (
        <LoadingState label="Loading service…" />
      ) : null}

      {error ? (
        <>
          <ErrorState message={error} onRetry={() => void load()} />
          <Link className="btn btn-sm" to="/">
            Back to stack status
          </Link>
        </>
      ) : null}

      {data ? <ServiceDetail key={trendsKey} data={data} /> : null}
    </>
  );
}

function ServiceMeta(props: { data: ServiceDetailPayload }) {
  const { container: c, presentation: p } = props.data;
  return (
    <>
      <StatusBadge value={c.status} />
      <span className="chip">{c.role}</span>
      {c.group ? <span className="chip">group {c.group}</span> : null}
      {c.service !== p.name ? (
        <code className="muted">{c.service}</code>
      ) : null}
      {p.external_urls?.length ? (
        <ExternalUrlLinks urls={p.external_urls} />
      ) : null}
    </>
  );
}
